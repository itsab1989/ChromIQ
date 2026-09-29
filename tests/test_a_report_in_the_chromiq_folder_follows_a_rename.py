"""B8-920: a report across projects that are NOT side by side lives in the
ChromIQ folder's ``reports/`` (K30, §24.4 of
``docs/design/measurement_report_limits.md``), and a rename or a run delete
of one of its projects must rewrite it like any other report that names the
project.

`core.report_refs.report_files_referring` searched the project, the folder
beside it and the projects beside it, but not the ChromIQ folder: a project
kept elsewhere (``<tmp>/elsewhere/Q``) never reached ``<ChromIQ>/reports``,
so after a rename the report went on naming ``Q``'s old folder and after a
run delete its old run numbers. And for the rename, the app's own reading of
the old folder (`resolve_recorded_folder`, seen from the ChromIQ folder)
cannot find a project that is neither beside it nor in it, so
`refers_here` refused the reference even once the file was searched.

Every test names its mutation; each was run red.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_beta38_challenge_fixes import _Settings           # noqa: E402
from tests.test_challenge_c_report_files import _Target           # noqa: E402
from tests.test_g7_reports_across_places import _read, _snapshot  # noqa: E402


def _project(folder: Path, name: str, runs: int = 3):
    """A project *name* in *folder* with *runs* measured runs."""
    from core.file_manager import Project, RunMeta
    from tests.test_import_measurement_module import _cgats, _PATCHES
    proj = Project.create(folder / name, name)
    for _ in range(runs - 1):
        proj.new_run()
    for run in proj.all_runs():
        run.ensure_dir()
        if not run.meta_path.exists():
            run.save_meta(RunMeta.fresh(run.id))
        (run.dir / f"{run.stem}.ti3").write_text(_cgats("CTI3", _PATCHES),
                                                 encoding="utf-8")
    return proj


def _report_across(places) -> Path:
    """A report across *places* (``[(project_root, run_id), ...]``), saved
    where `document_home` files it, as the window does."""
    from workflow.measurement_report import (document_file, document_home,
                                             document_measurement_key,
                                             new_document_id, save_report)
    members = []
    for i, (root, run) in enumerate(places, start=1):
        d = Path(root) / "runs" / run
        created = f"2026-0{i}-01T10:00:00"
        ti3 = f"{Path(root).name}.ti3"
        members.append({"dir": str(d), "created": created, "ti3": ti3,
                        "key": document_measurement_key(d, created, ti3)})
    body = document_file(doc_id=new_document_id(),
                         created="2026-06-01T10:00:00",
                         type_id="t0_printing_record", compliance=None,
                         detail=False, measurements=members,
                         scope="all_dates")
    home = document_home([m["dir"] for m in members])
    return save_report(body, home.parent)


def _dirs(f: Path) -> "list[str]":
    return [m["dir"] for m in _read(f)["document"]["measurements"]]


@pytest.fixture(params=["sub-folder", "outside"])
def two_places(request, tmp_path, monkeypatch):
    return _two_places(request.param, tmp_path, monkeypatch)


def _two_places(where: str, tmp_path, monkeypatch):
    """P in the ChromIQ folder, Q in another folder, and a report across
    both in ``<ChromIQ>/reports`` (§24.4). The other folder is either a
    sub-folder of the ChromIQ folder (K30: *"no matter if one of the
    projects, or both, are kept in sub folders"*; the only place the app
    opens a project in place) or a folder outside it."""
    import workflow.measurement_report as mr
    chromiq = tmp_path / "ChromIQ"
    elsewhere = (chromiq / "elsewhere" if where == "sub-folder"
                 else tmp_path / "elsewhere")
    chromiq.mkdir()
    elsewhere.mkdir()
    monkeypatch.setattr(mr, "chromiq_folder", lambda: chromiq)
    p = _project(chromiq, "P")
    q = _project(elsewhere, "Q")
    across = _report_across([(p.root, "run1"), (q.root, "run1"),
                             (q.root, "run3")])
    assert across.parent == chromiq / "reports", across
    return chromiq, elsewhere, p, q, across


def _delete(root: Path, run_id: str) -> None:
    import core.run_delete as rd
    from core.file_manager import Project
    proj = Project.load(root)
    plan = rd.plan_for(proj, _Target(run_id))
    assert plan.kind == rd.KIND_RUN, plan
    rd.delete_run(proj, plan)


def test_a_rename_of_the_project_elsewhere_rewrites_the_chromiq_folders_report(
        two_places):
    """Q (not in the ChromIQ folder) renamed to Q2: the report in
    ``<ChromIQ>/reports`` names ``elsewhere/Q2``; P's entry is untouched.

    MUTATION, proven red (1): drop the ChromIQ folder from
    `core.report_refs.report_files_referring` (the report still names Q).
    MUTATION, proven red (2), for Q outside the ChromIQ folder: drop the
    renamed-in-place rule from `refers_here` (the file is searched and the
    reference refused; in a sub-folder `resolve_recorded_folder` step 3c
    already finds the renamed project by its former name)."""
    from core.file_manager import FileManager
    chromiq, elsewhere, p, q, across = two_places
    q2 = FileManager(_Settings(chromiq)).rename_existing_project(q.root, "Q2")
    assert q2 == elsewhere / "Q2"
    assert _dirs(across) == [str(p.root / "runs" / "run1"),
                             str(q2 / "runs" / "run1"),
                             str(q2 / "runs" / "run3")]
    rec = _read(across)["document"]["measurements"]
    assert rec[1]["ti3"] == "Q2.ti3", rec[1]
    assert rec[1]["key"].startswith(str(q2 / "runs" / "run1") + "|"), rec[1]


def test_a_rename_of_the_project_in_the_chromiq_folder_rewrites_it_too(
        two_places):
    """P (in the ChromIQ folder, so the report is in the folder beside it)
    renamed to P2: that side already worked, and must keep working."""
    from core.file_manager import FileManager
    chromiq, elsewhere, p, q, across = two_places
    p2 = FileManager(_Settings(chromiq)).rename_existing_project(p.root, "P2")
    assert _dirs(across)[0] == str(p2 / "runs" / "run1")
    assert _dirs(across)[1:] == [str(q.root / "runs" / "run1"),
                                 str(q.root / "runs" / "run3")]


def test_a_run_delete_of_the_project_elsewhere_renumbers_the_report(
        two_places):
    """Run 2 of Q deleted: the report names Q's run1 and run2 (was run3).

    MUTATION, proven red: drop the ChromIQ folder from
    `report_files_referring` (the report still names runs/run3)."""
    chromiq, elsewhere, p, q, across = two_places
    _delete(q.root, "run2")
    assert _dirs(across) == [str(p.root / "runs" / "run1"),
                             str(q.root / "runs" / "run1"),
                             str(q.root / "runs" / "run2")]


def test_a_run_delete_of_the_project_elsewhere_marks_a_deleted_run(
        two_places):
    """Run 1 of Q deleted: its reference becomes ``run1.deleted`` and run 3
    becomes run 2, so neither can point at the run that took its number."""
    chromiq, elsewhere, p, q, across = two_places
    _delete(q.root, "run1")
    assert [Path(d).name for d in _dirs(across)] == ["run1", "run1.deleted",
                                                     "run2"]
    assert _dirs(across)[0] == str(p.root / "runs" / "run1")


def _unrelated_report(chromiq: Path, tmp_path: Path):
    """A report in ``<ChromIQ>/reports`` across two OTHER projects: one also
    called Q, in ``<tmp>/third`` (outside the ChromIQ folder), and R in a
    sub-folder of it."""
    third = tmp_path / "third"
    third.mkdir()
    other_q = _project(third, "Q")
    r = _project(chromiq / "Group", "R")
    other = _report_across([(other_q.root, "run1"), (other_q.root, "run3"),
                            (r.root, "run2")])
    assert other.parent == chromiq / "reports"
    return other_q, other


def test_an_unrelated_projects_report_in_the_chromiq_folder_is_untouched(
        two_places, tmp_path):
    """The other Q still exists where the report recorded it: its report is
    not a byte different after our Q loses a run and is renamed.

    MUTATION, proven red (sub-folder): drop the "recorded folder is another
    existing project" test from `refers_here`. `resolve_recorded_folder`
    step 3c searches the ChromIQ folder for the ONE project called Q before
    it ever looks at the recorded folder, so without that test the other
    Q's entries are renumbered and renamed to Q2."""
    from core.file_manager import FileManager
    chromiq, elsewhere, p, q, across = two_places
    other_q, other = _unrelated_report(chromiq, tmp_path)
    before = other.read_bytes()
    _delete(q.root, "run2")
    assert other.read_bytes() == before
    FileManager(_Settings(chromiq)).rename_existing_project(q.root, "Q2")
    assert other.read_bytes() == before
    assert "/elsewhere/Q2/runs/" in _dirs(across)[1]


def test_a_vanished_namesake_outside_is_not_taken_for_a_rename(
        tmp_path, monkeypatch):
    """The other Q (outside the ChromIQ folder) has since been deleted in
    Finder, so its recorded folder is on no disk, as a renamed project's
    is. Our Q is kept outside as well: the renamed-in-place rule must not
    claim a folder that was never beside it.

    Only for our Q OUTSIDE the ChromIQ folder: with our Q in a sub-folder,
    the app's own reading (`resolve_recorded_folder` step 3c, B8-919) gives
    the vanished Q's references to the ONE project in the ChromIQ folder
    that is called Q, and the rewrite follows the app's reading.

    MUTATION, proven red: drop the ``prefix`` test of the renamed-in-place
    rule in `refers_here` (the other Q's entries are renumbered, then
    renamed to Q2)."""
    from core.file_manager import FileManager
    chromiq, elsewhere, p, q, across = _two_places("outside", tmp_path,
                                                   monkeypatch)
    other_q, other = _unrelated_report(chromiq, tmp_path)
    shutil.rmtree(other_q.root)
    before = other.read_bytes()
    _delete(q.root, "run2")
    assert other.read_bytes() == before
    FileManager(_Settings(chromiq)).rename_existing_project(q.root, "Q2")
    assert other.read_bytes() == before
    assert "/elsewhere/Q2/runs/" in _dirs(across)[1]


def test_nothing_under_the_chromiq_folders_old_is_rewritten(two_places):
    """An archive in ``<ChromIQ>/old/<stamp>/`` is history: untouched."""
    from core.file_manager import FileManager
    chromiq, elsewhere, p, q, across = two_places
    arch = chromiq / "old" / "2026-06-01_10-00-00"
    arch.mkdir(parents=True)
    kept = arch / across.name
    kept.write_bytes(across.read_bytes())
    before = _snapshot(chromiq / "old")
    FileManager(_Settings(chromiq)).rename_existing_project(q.root, "Q2")
    assert _snapshot(chromiq / "old") == before
    assert json.loads(kept.read_text(encoding="utf-8"))["document"]["measurements"][1][
        "dir"].endswith("/elsewhere/Q/runs/run1")
