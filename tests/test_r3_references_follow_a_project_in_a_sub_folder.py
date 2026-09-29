"""Second check R3, beta 39 (B8-923, B8-924): a project moved into a
sub-folder of the ChromIQ folder (§24.4) loses a run or is renamed, and the
reports of OTHER projects that name it follow.

`core.report_refs.report_files_referring` searched the project, the folder
across projects beside it, ``<ChromIQ>/reports`` and the projects BESIDE it.
In ``<ChromIQ>/Group/`` the projects beside it are only Group's, so every
other project's reports (P in the ChromIQ folder, R in ``Other/``) and the
folder across projects it was moved out of (``Other/reports``) were never
searched: after a run delete they still named ``runs/run1``, and their
windows loaded the former run 2 as that report's measurement; after a rename
they kept the old name, and a fresh project of that name then captured them.

The app finds the moved project from every one of those reports
(`resolve_recorded_folder`, step 3c), so the rewrite now searches every
project it could be named from, and `refers_here` still decides which
reference is this project's.

Every test names its mutation; each was run red.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_a_report_in_the_chromiq_folder_follows_a_rename import (  # noqa: E402
    _delete, _project, _report_across)
from tests.test_beta38_challenge_fixes import _Settings           # noqa: E402
from tests.test_g7_reports_across_places import _read, _snapshot  # noqa: E402


def _record_in(report: Path, folder: Path) -> Path:
    """A verdict record of *report* in *folder* (``.../reports``): the same
    document list, as the window writes into every covered folder."""
    folder.mkdir(parents=True, exist_ok=True)
    rec = folder / report.name
    rec.write_bytes(report.read_bytes())
    return rec


def _dirs(f: Path) -> "list[str]":
    return [m["dir"] for m in _read(f)["document"]["measurements"]]


@pytest.fixture
def moved(tmp_path, monkeypatch):
    """P in the ChromIQ folder, R and Q side by side in ``Other/``; a report
    across R and Q in ``Other/reports`` (with a record in R's run1), and one
    across P and Q in ``<ChromIQ>/reports`` (with a record in P's run1).
    Then Q is moved into ``Group/`` in Finder, as the tester did."""
    import workflow.measurement_report as mr
    chromiq = tmp_path / "ChromIQ"
    (chromiq / "Other").mkdir(parents=True)
    (chromiq / "Group").mkdir()
    monkeypatch.setattr(mr, "chromiq_folder", lambda: chromiq)
    p = _project(chromiq, "P")
    r = _project(chromiq / "Other", "R")
    q = _project(chromiq / "Other", "Q")
    beside = _report_across([(r.root, "run1"), (q.root, "run1"),
                             (q.root, "run2")])
    assert beside.parent == chromiq / "Other" / "reports", beside
    across = _report_across([(p.root, "run1"), (q.root, "run1"),
                             (q.root, "run3")])
    assert across.parent == chromiq / "reports", across
    rec_r = _record_in(beside, r.root / "runs" / "run1" / "reports")
    rec_p = _record_in(across, p.root / "runs" / "run1" / "reports")
    q_now = chromiq / "Group" / "Q"
    shutil.move(str(q.root), str(q_now))
    return {"chromiq": chromiq, "p": p.root, "r": r.root, "q": q_now,
            "old_q": q.root, "beside": beside, "across": across,
            "rec_r": rec_r, "rec_p": rec_p}


def test_the_app_finds_the_moved_project_from_every_other_report(moved):
    """The premise: every report the rewrite must now reach is one from
    which the app ALREADY reads the moved project (step 3c), so it would
    load Q's current runs through the stale numbers."""
    from workflow.measurement_report import (project_home_of,
                                             resolve_recorded_folder)
    for f in ("beside", "across", "rec_r", "rec_p"):
        home = project_home_of(moved[f].parent)
        homes = [home] if home is not None else [moved[f].parent]
        got = resolve_recorded_folder(_dirs(moved[f])[1], homes,
                                      must_exist=False)
        assert got == moved["q"] / "runs" / "run1", (f, got)


def test_a_run_delete_in_a_sub_folder_renumbers_every_other_projects_report(
        moved):
    """Run 1 of Group/Q deleted: every report naming it, in P, in R, in
    ``Other/reports`` and in ``<ChromIQ>/reports``, says ``run1.deleted``
    for it and ``run1`` for the former run 2; P's and R's own entries do
    not move.

    MUTATION, proven red: `report_files_referring` searching only the
    projects beside the project (the pre-R3 rule): P's and R's records and
    ``Other/reports`` keep ``runs/run1`` and ``runs/run2``."""
    _delete(moved["q"], "run1")
    old = str(moved["old_q"])
    for f, own in (("beside", moved["r"]), ("rec_r", moved["r"])):
        assert _dirs(moved[f]) == [str(own / "runs" / "run1"),
                                   old + "/runs/run1.deleted",
                                   old + "/runs/run1"], f
    for f, own in (("across", moved["p"]), ("rec_p", moved["p"])):
        assert _dirs(moved[f]) == [str(own / "runs" / "run1"),
                                   old + "/runs/run1.deleted",
                                   old + "/runs/run2"], f


def test_after_the_delete_no_other_report_loads_the_former_run_2(moved):
    """What the window reads through the rewritten reference: the deleted
    run is on no disk, and no reference lands on the run that took its
    number."""
    from workflow.measurement_report import (project_home_of,
                                             resolve_recorded_folder)
    _delete(moved["q"], "run1")
    for f in ("beside", "across", "rec_r", "rec_p"):
        home = project_home_of(moved[f].parent)
        homes = [home] if home is not None else [moved[f].parent]
        got = resolve_recorded_folder(_dirs(moved[f])[1], homes)
        assert got is None or not got.is_dir(), (f, got)


def test_a_rename_in_a_sub_folder_rewrites_every_other_projects_report(
        moved):
    """Group/Q renamed to Q2 (Rename the project): every report naming it
    names Q2, with Q2's file name (the recorded folder above it is kept, as
    every rename does; the app finds Q2 in ``Group/`` by that name), and
    P's and R's own entries are untouched.

    MUTATION, proven red: the pre-R3 `report_files_referring` (P's and R's
    records and ``Other/reports`` keep ``Other/Q``)."""
    from core.file_manager import FileManager
    q2 = FileManager(_Settings(moved["chromiq"])).rename_existing_project(
        moved["q"], "Q2")
    assert q2 == moved["chromiq"] / "Group" / "Q2"
    for f in ("beside", "across", "rec_r", "rec_p"):
        rec = _read(moved[f])["document"]["measurements"]
        assert "/Q2/runs/" in rec[1]["dir"] and "/Q2/runs/" in rec[2]["dir"], (
            f, rec)
        assert rec[1]["ti3"] == "Q2.ti3", (f, rec[1])
        assert not rec[0]["dir"].split("/runs/")[0].endswith("/Q"), (f, rec)


def test_a_fresh_project_of_the_old_name_captures_nothing_after_a_rename(
        moved):
    """SUB2: after the rename, a fresh project Q in the ChromIQ folder's
    top level. The other projects' reports go on reading Group/Q2, and a
    run delete of Q2 renumbers them; the fresh Q's own reports and the
    references to it are never touched.

    MUTATION, proven red: the pre-R3 `report_files_referring` (the
    references keep ``Other/Q``; resolved from P they land on the fresh
    ``<ChromIQ>/Q``, and Q2's delete leaves them at ``run1``)."""
    from core.file_manager import FileManager
    from workflow.measurement_report import (project_home_of,
                                             resolve_recorded_folder)
    chromiq = moved["chromiq"]
    q2 = FileManager(_Settings(chromiq)).rename_existing_project(
        moved["q"], "Q2")
    fresh = _project(chromiq, "Q")
    own = _report_across([(fresh.root, "run1"), (fresh.root, "run2")])
    before_fresh = _snapshot(fresh.root)
    before_own = own.read_bytes()
    for f in ("across", "rec_p", "rec_r"):
        home = project_home_of(moved[f].parent)
        homes = [home] if home is not None else [moved[f].parent]
        got = resolve_recorded_folder(_dirs(moved[f])[1], homes)
        assert got == q2 / "runs" / "run1", (f, got)
    _delete(q2, "run1")
    for f in ("beside", "across", "rec_r", "rec_p"):
        assert _dirs(moved[f])[1].endswith("/Q2/runs/run1.deleted"), f
    assert _snapshot(fresh.root) == before_fresh
    assert own.read_bytes() == before_own


def test_a_namesake_in_another_sub_folder_is_never_rewritten(moved):
    """A DIFFERENT project called Q in ``Third/``, with a report across it
    and P in ``<ChromIQ>/reports`` and a record in its own run. Group/Q's
    run delete and rename change neither.

    MUTATION, proven red: `_renumber_entry` without its `refers_here`
    test, renumbering by name (the other Q's report and record, now searched,
    are renumbered). Dropping only the "recorded folder is another existing
    project" test stays green here: two projects answer to Q, so the app's
    own reading (step 3c) claims neither."""
    from core.file_manager import FileManager
    chromiq = moved["chromiq"]
    other = _project(chromiq / "Third", "Q")
    rep = _report_across([(moved["p"], "run2"), (other.root, "run1"),
                          (other.root, "run2")])
    rec = _record_in(rep, other.root / "runs" / "run1" / "reports")
    before = (rep.read_bytes(), rec.read_bytes())
    _delete(moved["q"], "run1")
    assert (rep.read_bytes(), rec.read_bytes()) == before
    FileManager(_Settings(chromiq)).rename_existing_project(moved["q"], "Q2")
    assert (rep.read_bytes(), rec.read_bytes()) == before


def test_each_file_is_searched_once_and_archives_never(moved):
    """The search lists every report file once, and nothing under an
    ``old/`` folder."""
    from core.report_refs import report_files_referring
    chromiq = moved["chromiq"]
    arch = chromiq / "old" / "2026-06-01_10-00-00" / "reports"
    arch.mkdir(parents=True)
    (arch / moved["across"].name).write_bytes(moved["across"].read_bytes())
    parch = moved["p"] / "reports" / "old" / "x"
    parch.mkdir(parents=True)
    (parch / moved["across"].name).write_bytes(moved["across"].read_bytes())
    files = report_files_referring(moved["q"])
    real = [os.path.realpath(str(f)) for f in files]
    assert len(real) == len(set(real)), files
    assert not any("/old/" in f for f in real), files
    for f in ("beside", "across", "rec_r", "rec_p"):
        assert os.path.realpath(str(moved[f])) in real, f


def test_the_normal_layout_still_follows(tmp_path, monkeypatch):
    """Side by side in the ChromIQ folder (no sub-folder): a run delete
    still renumbers the other project's record and the folder across
    projects, exactly as before."""
    import workflow.measurement_report as mr
    chromiq = tmp_path / "ChromIQ"
    chromiq.mkdir()
    monkeypatch.setattr(mr, "chromiq_folder", lambda: chromiq)
    p = _project(chromiq, "P")
    q = _project(chromiq, "Q")
    across = _report_across([(p.root, "run1"), (q.root, "run1"),
                             (q.root, "run2")])
    rec = _record_in(across, p.root / "runs" / "run1" / "reports")
    _delete(q.root, "run1")
    for f in (across, rec):
        assert [Path(d).name for d in _dirs(f)] == ["run1", "run1.deleted",
                                                    "run1"], f
        assert json.loads(f.read_text(encoding="utf-8"))
