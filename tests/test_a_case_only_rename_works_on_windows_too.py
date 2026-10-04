"""A rename that changes only the CASE of a project's name renames its folder
on Windows too (CI round 2, Windows x64 and arm64).

``WindowsPath.__eq__`` compares case-folded: "Demo-Proj" and "demo-proj" are
EQUAL paths there and different paths on macOS and Linux. Three places asked
``new_root == old_root`` to mean "the user typed the same name"
(`FileManager.rename_existing_project` and the two rename doors in
`ui/tabs/tab_chart.py`), so on Windows a case-only rename was taken for no
rename at all: the folder kept "Demo-Proj" while its files and project.json
were renamed to "demo-proj" (measured on the Windows runner by
`test_beta38_challenge_fixes.py::test_the_ordinary_rename_changes_the_case_of_the_folder_too`).

They now ask `same_spelling`, which is ``str(a) == str(b)``: what ``==``
already is on POSIX, so macOS and Linux do exactly what they did.

The trap is played on any host with a Path whose ``==`` folds case the way
Windows' does, on a case-insensitive volume (the macOS default).

MUTATION, proven red: put ``new_root == old_root`` back in
`rename_existing_project`: the folder keeps "Demo-Proj".
"""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest


def test_windows_paths_really_are_equal_across_case():
    """The premise, asked of pathlib itself on any host."""
    assert PureWindowsPath("C:/x/Demo-Proj") == PureWindowsPath("C:/x/demo-proj")
    assert PurePosixPath("/x/Demo-Proj") != PurePosixPath("/x/demo-proj")


def test_same_spelling_is_posix_equality_and_sees_case_on_windows():
    from core.file_manager import same_spelling
    for a, b in [("/x/Demo-Proj", "/x/demo-proj"), ("/x/a", "/x/a"),
                 ("/x/a", "/x/b"), ("/x/Ä", "/x/ä")]:
        assert same_spelling(PurePosixPath(a), PurePosixPath(b)) == (
            PurePosixPath(a) == PurePosixPath(b))
    assert not same_spelling(PureWindowsPath("C:/x/Demo-Proj"),
                             PureWindowsPath("C:/x/demo-proj"))
    assert same_spelling(PureWindowsPath("C:/x/Demo"), PureWindowsPath("C:/x/Demo"))


class _CaseBlindPath(type(Path())):
    """A real, usable path whose ``==`` folds case as WindowsPath's does."""

    def __eq__(self, other):
        return str(self).casefold() == str(other).casefold()

    def __hash__(self):
        return hash(str(self).casefold())


def _case_insensitive(where: Path) -> bool:
    probe = where / "CaseProbe"
    probe.write_text("x", encoding="utf-8")
    try:
        return (where / "caseprobe").exists()
    finally:
        probe.unlink()


class _Settings:
    def __init__(self, root: Path) -> None:
        self._root = root

    def get(self, key, default=None):
        return str(self._root) if key == "custom_output_path" else default


def test_a_case_only_rename_moves_the_folder_when_paths_compare_like_windows(
        tmp_path, monkeypatch):
    import core.file_manager as fm_mod
    from core.file_manager import FileManager, Project
    if not _case_insensitive(tmp_path):
        pytest.skip("this volume is case-sensitive; a case-only rename is an "
                    "ordinary rename on it")
    proj = Project.create(tmp_path / "Demo-Proj", "Demo-Proj")
    run = proj.current_run()
    run.ensure_dir()
    run.profile_icc.write_bytes(b"THE-BUILT-PROFILE")
    old = _CaseBlindPath(tmp_path / "Demo-Proj")
    assert old == old.parent / "demo-proj"          # the Windows trap, here
    # `rename_existing_project` rebuilds its argument with `Path(...)`, so the
    # module's `Path` is the case-blind one for this call, as on Windows.
    monkeypatch.setattr(fm_mod, "Path", _CaseBlindPath)
    new = FileManager(_Settings(tmp_path)).rename_existing_project(
        old, "demo-proj")
    assert os.listdir(tmp_path) == ["demo-proj"]
    assert str(new) == str(tmp_path / "demo-proj")
    assert (tmp_path / "demo-proj" / "runs" / "run1").is_dir()
    assert "demo-proj.icc" in os.listdir(tmp_path / "demo-proj" / "runs" / "run1")


def test_the_two_rename_doors_in_the_chart_tab_ask_the_spelling():
    """Both doors that decide "nothing to rename" compare spellings, not
    Path equality (read from the source: they need a whole tab to drive)."""
    import inspect
    from ui.tabs.tab_chart import TabChart
    for name in ("_handle_target_rename",):
        src = inspect.getsource(getattr(TabChart, name))
        assert "new_root == old_root" not in src, name
        assert "_same_spelling(new_root, old_root)" in src, name
    src = inspect.getsource(TabChart)
    assert "new_root == old_root" not in src
