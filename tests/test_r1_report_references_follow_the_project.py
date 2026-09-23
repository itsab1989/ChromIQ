"""Re-challenge R1 of beta 39, #1 and #2: a run delete and a rename rewrite
the saved reports of THIS project only.

The tester (``~/Desktop/ChromIQ-beta39-proof/rechallenge-R1-behaviour/
REPORT.md``) found, on screen:

1. a Finder duplicate "X copy", renamed, then its profile run 2 deleted from
   the bar: 14 report files of the ORIGINAL X were renumbered;
2. "Folders" renamed to "Folders-Renamed", a fresh project given the old
   name beside it, then run 1 of Folders-Renamed deleted: all 30 reports of
   the fresh, unrelated project were renumbered.

Both came from matching a reference by NAME (the folder, the files and
``former_names``) in every project beside it and in the folder across
projects. `core.report_refs.refers_here` now asks the app's own reading of
the reference (`resolve_recorded_folder`) whose folder it is.

Every test names its mutation; each was run red (REPORT.md in
``~/Desktop/ChromIQ-beta39-proof/rechallenge-R1-fixes/``).
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_beta38_challenge_fixes import _Settings           # noqa: E402
from tests.test_challenge_c_report_files import (                 # noqa: E402
    _Target, _run_dirs, _three_runs)
from tests.test_g7_reports_across_places import _read, _snapshot  # noqa: E402


def _across_folder_report(tmp_path: Path, project: Path, runs) -> Path:
    """A report in ``<tmp>/reports`` covering *project*'s *runs*, as the
    window writes one across projects: recorded by absolute folder."""
    from workflow.measurement_report import (document_file,
                                             document_measurement_key,
                                             new_document_id, save_report)
    members = []
    for i, r in enumerate(runs, start=1):
        d = project / "runs" / r
        created = f"2026-0{i}-01T10:00:00"
        ti3 = f"{project.name}.ti3"
        members.append({"dir": str(d), "created": created, "ti3": ti3,
                        "key": document_measurement_key(d, created, ti3)})
    body = document_file(doc_id=new_document_id(),
                         created="2026-06-01T10:00:00",
                         type_id="t0_printing_record", compliance=None,
                         detail=False, measurements=members,
                         scope="all_dates")
    new = save_report(body, tmp_path)
    assert new.parent == tmp_path / "reports", new
    return new


def _delete(root: Path, run_id: str) -> None:
    import core.run_delete as rd
    from core.file_manager import Project
    proj = Project.load(root)
    plan = rd.plan_for(proj, _Target(run_id))
    assert plan.kind == rd.KIND_RUN, plan
    rd.delete_run(proj, plan)


def test_deleting_a_run_of_a_renamed_duplicate_leaves_the_original_alone(
        tmp_path):
    """#1. "P copy" (a Finder duplicate of P) renamed to "P-copy": its
    former name is P, which is the ORIGINAL's folder beside it. Run 2 of the
    copy deleted: no byte of P, nor of the report across projects that
    names P, changes; the copy's own reports are renumbered.

    MUTATION, proven red: in `core.report_refs._renumber_entry` drop the
    ``if here is not None and not here(m)`` test (P's own reports and the
    report across projects are renumbered, as on screen)."""
    from core.file_manager import FileManager
    proj = _three_runs(tmp_path)
    across = _across_folder_report(tmp_path, proj.root, ["run1", "run3"])
    shutil.copytree(proj.root, tmp_path / "P copy")
    copy = FileManager(_Settings(tmp_path)).rename_existing_project(
        tmp_path / "P copy", "P copy")
    assert copy == tmp_path / "P-copy"
    man = json.loads((copy / "project.json").read_text(encoding="utf-8"))
    assert "P" in man["former_names"], man
    before = _snapshot(proj.root, tmp_path / "reports")
    _delete(copy, "run2")
    assert _snapshot(proj.root, tmp_path / "reports") == before
    assert _run_dirs(across) == ["run1", "run3"]
    own = sorted((copy / "runs" / "run2" / "reports").glob("report_*"))
    assert own and _run_dirs(own[0]) == ["run2"], _run_dirs(own[0])
    whole = sorted((copy / "reports").glob("report_*.json"))
    assert _run_dirs(whole[0]) == ["run1", "run2.deleted", "run2"]


def test_deleting_a_run_leaves_a_new_project_with_the_former_name_alone(
        tmp_path):
    """#2. P renamed to R (former name P), then a NEW project P made beside
    it, with its own reports and a report across projects naming it. Run 1
    of R deleted: no byte of the new P, nor of that report, changes.

    MUTATION, proven red: as above, drop the ``here`` test in
    `_renumber_entry` (every report of the new P is renumbered)."""
    from core.file_manager import FileManager
    old = _three_runs(tmp_path)
    r = FileManager(_Settings(tmp_path)).rename_existing_project(old.root, "R")
    assert r == tmp_path / "R" and not (tmp_path / "P").exists()
    fresh = _three_runs(tmp_path)                    # a new "P"
    across = _across_folder_report(tmp_path, fresh.root, ["run2", "run3"])
    before = _snapshot(fresh.root, tmp_path / "reports")
    _delete(r, "run1")
    assert _snapshot(fresh.root, tmp_path / "reports") == before
    assert _run_dirs(across) == ["run2", "run3"]
    own = sorted((r / "runs" / "run1" / "reports").glob("report_*"))
    assert own and _run_dirs(own[0]) == ["run1"], _run_dirs(own[0])


def test_deleting_a_run_still_renumbers_this_projects_references_elsewhere(
        tmp_path):
    """The normal case, so the fix cannot pass by rewriting nothing: P's
    run 2 deleted; the report across projects that names P's runs 1 and 3,
    and P's own report across its runs, are renumbered.

    MUTATION, proven red: make `core.report_refs.refers_here`'s test return
    False (nothing outside the run folders is renumbered)."""
    proj = _three_runs(tmp_path)
    across = _across_folder_report(tmp_path, proj.root, ["run1", "run2",
                                                         "run3"])
    _delete(proj.root, "run2")
    assert _run_dirs(across) == ["run1", "run2.deleted", "run2"]
    keys = [m["key"] for m in _read(across)["document"]["measurements"]]
    assert "/runs/run2.deleted|" in keys[1], keys
    whole = sorted((proj.root / "reports").glob("report_*.json"))
    assert _run_dirs(whole[0]) == ["run1", "run2.deleted", "run2"]


def test_renaming_an_original_leaves_its_duplicates_reports_alone(tmp_path):
    """The rename's rewrite, audited the same way. "P copy" is a Finder
    duplicate of P that was never renamed: its files still carry P's name,
    and so do its reports. P renamed to Z: the copy's reports still name P
    (they are the copy's), P's own reports name Z.

    MUTATION, proven red: in `core.report_refs._rename_entry` drop the
    ``here`` test (the copy's reports are rewritten to name Z, because P's
    folder no longer exists and ``_free`` let the old name through)."""
    from core.file_manager import FileManager
    proj = _three_runs(tmp_path)
    shutil.copytree(proj.root, tmp_path / "P copy")
    copy = tmp_path / "P copy"
    before = _snapshot(copy)
    z = FileManager(_Settings(tmp_path)).rename_existing_project(proj.root,
                                                                 "Z")
    assert _snapshot(copy) == before
    whole = sorted((z / "reports").glob("report_*.json"))
    dirs = [m["dir"] for m in _read(whole[0])["document"]["measurements"]]
    assert all("/Z/runs/" in d for d in dirs), dirs


def test_renaming_rewrites_the_report_across_projects_that_names_it(tmp_path):
    """The rename's normal case: a report in ``<tmp>/reports`` naming P is
    rewritten to name Z.

    MUTATION, proven red: make `refers_here`'s test return False."""
    from core.file_manager import FileManager
    proj = _three_runs(tmp_path)
    across = _across_folder_report(tmp_path, proj.root, ["run1", "run2"])
    FileManager(_Settings(tmp_path)).rename_existing_project(proj.root, "Z")
    dirs = [m["dir"] for m in _read(across)["document"]["measurements"]]
    assert all("/Z/runs/" in d for d in dirs), dirs
