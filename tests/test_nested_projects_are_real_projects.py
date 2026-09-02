"""A project in a sub-folder of the ChromIQ folder is a project like any other.

The folder model has always allowed one (`FileManager.open_project_at`, and
`set_target_name` keeps such a project where it is) — Knut asked on 2026-08-27
how one is CREATED, which is a separate question. What this file locks down is
that the ones that already exist are not quietly second-class:

  * `resolved_root_for_name` answers where the build will really go, while
    `preview_project_root` answers `<ChromIQ>/<name>` and is blind to depth;
  * renaming one works, keeps it in its group, and keeps the app pointed at it —
    it used to raise `FileNotFoundError`, which the caller answered by "creating
    fresh instead": an empty project at the new name and the real one abandoned;
  * the "you have already built this profile" guard sees its ICC — it answered
    False, so the guard never fired;
  * "Delete the whole project" can delete one — it refused with a log line.

All four measured on a real project before the fix.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import FileManager, Project, same_dir   # noqa: E402
from core.settings import DEFAULTS                              # noqa: E402


class _Settings:
    def __init__(self, tmp):
        self.d = dict(DEFAULTS)
        self.d["custom_output_path"] = str(tmp)

    def get(self, k, d=None):
        return self.d.get(k, d)

    def set(self, k, v):
        self.d[k] = v


@pytest.fixture
def nested(tmp_path):
    """A project at ``<ChromIQ>/Group-A/Baryta`` with a built profile in it."""
    fm = FileManager(_Settings(tmp_path))
    root = tmp_path / "Group-A" / "Baryta"
    root.parent.mkdir(parents=True)
    proj = Project.create(root, "Baryta")
    run = proj.current_run()
    (run.dir / f"{run.stem}.icc").write_text("a finished profile", encoding="utf-8")
    fm.open_project_at(root)
    return fm, root


def test_the_name_resolves_where_the_build_will_go(nested, tmp_path):
    fm, root = nested
    assert fm.resolved_root_for_name("Baryta") == root
    assert fm.preview_project_root("Baryta") == tmp_path / "Baryta", \
        "preview_project_root is supposed to stay the top-level answer"
    assert same_dir(fm.working_dir(), root)


def test_a_different_name_still_resolves_to_the_top_level(nested, tmp_path):
    """The override applies to THIS project's name and to nothing else."""
    fm, _root = nested
    assert fm.resolved_root_for_name("Something-Else") == tmp_path / "Something-Else"


def test_the_built_profile_guard_sees_the_profile(nested):
    fm, _root = nested
    assert fm.project_has_built_profile("Baryta") is True


def test_renaming_keeps_the_project_in_its_group_and_in_view(nested, tmp_path):
    fm, root = nested
    new = fm.rename_existing_project("Baryta", "Baryta-2")
    assert new == tmp_path / "Group-A" / "Baryta-2"
    assert new.exists() and not root.exists()
    assert (new / "runs" / "run1" / "Baryta-2.icc").exists(), \
        "the artefact stems did not follow the rename"
    assert fm.project_root_override() == new, "the app lost sight of it"
    assert same_dir(fm.working_dir(), new)


def test_deleting_a_nested_project_works(nested):
    fm, root = nested
    fm.delete_project_folder("Baryta")
    assert not root.exists()


def test_the_delete_guard_still_refuses_what_it_should(nested, tmp_path, caplog):
    """The safety this guard exists for is unchanged: inside the ChromIQ folder,
    not the folder itself, and carrying a manifest."""
    fm, _root = nested
    fm.delete_project_folder("")                       # no name
    (tmp_path / "not-a-project").mkdir()
    fm.delete_project_folder("not-a-project")          # no manifest
    assert (tmp_path / "not-a-project").exists()
    assert tmp_path.exists()
