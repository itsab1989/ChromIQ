"""#130 (Knut, 2026-07-27): renaming a project must not strand the real file.

ChromIQ's own artefacts all carry the project stem, so a folder can only hold a
file already named what a rename needs if someone put it there by hand. That
used to make the rename skip the genuine file — which then kept the old name for
good, while the project silently used the stranger. The stranger is moved aside
instead.
"""
from __future__ import annotations

import shutil

from core.file_manager import CONFLICT_MARKER, Project


def _project_with_conflict(tmp_path, name="Alpha", clash="Beta"):
    proj = Project.create(tmp_path / name, name)
    run = proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_text("the real chart")
    (run.dir / f"{clash}.ti2").write_text("a stranger")
    return proj, run


def test_the_real_file_keeps_the_projects_name(tmp_path):
    _project_with_conflict(tmp_path)
    shutil.move(str(tmp_path / "Alpha"), str(tmp_path / "Beta"))

    Project.load(tmp_path / "Beta").rename("Beta")

    d = tmp_path / "Beta" / "runs" / "run1"
    assert (d / "Beta.ti2").read_text() == "the real chart"


def test_the_stranger_is_kept_under_a_name_that_explains_itself(tmp_path):
    _project_with_conflict(tmp_path)
    shutil.move(str(tmp_path / "Alpha"), str(tmp_path / "Beta"))
    Project.load(tmp_path / "Beta").rename("Beta")

    d = tmp_path / "Beta" / "runs" / "run1"
    aside = d / f"Beta{CONFLICT_MARKER}.ti2"
    assert aside.exists(), sorted(x.name for x in d.iterdir())
    assert aside.read_text() == "a stranger", "nothing may be lost"


def test_no_file_is_left_under_the_old_name(tmp_path):
    """The old failure: the genuine chart stayed behind as Alpha.ti2 forever."""
    _project_with_conflict(tmp_path)
    shutil.move(str(tmp_path / "Alpha"), str(tmp_path / "Beta"))
    Project.load(tmp_path / "Beta").rename("Beta")

    assert not (tmp_path / "Beta" / "runs" / "run1" / "Alpha.ti2").exists()


def test_renaming_twice_does_not_overwrite_the_first_file_moved_aside(tmp_path):
    """A second collision must not silently replace the first stranger."""
    _project_with_conflict(tmp_path)
    shutil.move(str(tmp_path / "Alpha"), str(tmp_path / "Beta"))
    Project.load(tmp_path / "Beta").rename("Beta")

    d = tmp_path / "Beta" / "runs" / "run1"
    (d / "Gamma.ti2").write_text("a second stranger")
    shutil.move(str(tmp_path / "Beta"), str(tmp_path / "Gamma"))
    Project.load(tmp_path / "Gamma").rename("Gamma")

    d = tmp_path / "Gamma" / "runs" / "run1"
    assert (d / "Gamma.ti2").read_text() == "the real chart"
    kept = sorted(p.read_text() for p in d.glob(f"*{CONFLICT_MARKER}*.ti2"))
    assert kept == ["a second stranger", "a stranger"], kept


def test_an_ordinary_rename_is_untouched_by_any_of_this(tmp_path):
    proj = Project.create(tmp_path / "Solo", "Solo")
    run = proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_text("chart")
    shutil.move(str(tmp_path / "Solo"), str(tmp_path / "Duo"))
    Project.load(tmp_path / "Duo").rename("Duo")

    d = tmp_path / "Duo" / "runs" / "run1"
    assert (d / "Duo.ti2").read_text() == "chart"
    assert not list(d.glob(f"*{CONFLICT_MARKER}*"))


def test_the_marker_is_safe_on_every_platform():
    """Underscores rather than parentheses, which some shells and tools treat
    specially (Knut raised the same concern)."""
    assert CONFLICT_MARKER == "_conflicted_at_renaming_procedure"
    assert not set(CONFLICT_MARKER) & set(' ()[]{}*?"<>|:/\\')
