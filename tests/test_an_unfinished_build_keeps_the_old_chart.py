"""F4: a chart build that does not finish must not destroy the chart it replaces.

`Run.reset_chart_artefacts` runs BEFORE targen, and its own docstring said the
chart files "are regenerated, so they may be dropped". They are only regenerated
if the build finishes. Measured on screen, 2026-08-28: pressing GENERATE CHART
on a run whose chart had been printed but not yet measured, then closing the
window mid-build, left seven files gone — `.ti2` among them — with nothing
archived and no window shown.

WHY THAT IS UNRECOVERABLE, and not merely annoying:
* `chartread` reads a printed sheet against its `.ti2`. Without it the printed
  pages are waste paper.
* A chart is laid out from a random seed which ChromIQ restores FROM the `.ti2`.
  Once it is gone, rebuilding from identical settings produces a different
  chart that no longer matches the paper on the desk.
* The "Restore Used Chart" copy is only made when a MEASUREMENT starts, so the
  window between printed and measured — the one the app tells people to spend
  waiting for the ink to dry — is exactly the window with no copy.

The chart is set aside rather than archived to `old/`: Knut ruled at beta.148
that only measurements belong there, or `old/` stops being readable, and a run
with nothing to lose must not spawn an `old/` folder at all.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import Project                          # noqa: E402


@pytest.fixture()
def run_with_a_chart(tmp_path):
    proj = Project.create(tmp_path / "Proj", "Proj")
    run = proj.current_run()
    for name in (f"{run.stem}.ti1", f"{run.stem}.ti2",
                 f"{run.stem}.channels.json",
                 f"{run.stem}_01.tif", f"{run.stem}_02.tif"):
        (run.dir / name).write_text(f"the chart's {name}")
    return proj, run


def _files(run):
    return sorted(p.name for p in run.dir.iterdir() if p.is_file())


def test_a_build_that_fails_puts_the_whole_chart_back(run_with_a_chart):
    _proj, run = run_with_a_chart
    before = _files(run)
    stash = run.reset_chart_artefacts(stash=True)
    assert stash is not None and stash.is_dir()
    assert _files(run) == ["meta.json"], "the run should be clear during a build"
    run.settle_chart_stash(stash, built=False)
    assert _files(run) == before
    assert (run.dir / f"{run.stem}.ti2").read_text().endswith(".ti2"), \
        "the .ti2 came back as something else"
    assert not run.chart_stash_dirs()


def test_the_app_closing_mid_build_is_repaired_when_the_project_reopens(
        run_with_a_chart):
    """Nothing settles the stash when the process dies — and closing the window
    is precisely what a person does to escape a build, because there is no Stop
    button. So the next open has to do it."""
    proj, run = run_with_a_chart
    before = _files(run)
    run.reset_chart_artefacts(stash=True)          # …and then the app is gone
    assert run.chart_stash_dirs()

    reopened = Project.load(proj.root)
    again = reopened.all_runs()[0]
    assert _files(again) == before
    assert not again.chart_stash_dirs(), "the stash was left behind"


def test_a_build_that_SUCCEEDS_does_not_resurrect_the_old_chart(run_with_a_chart):
    """The negative control. Putting a chart back unconditionally would be its
    own fault: a new chart with fewer pages would keep the extra sheets of the
    old one, and the run would hold two charts at once."""
    _proj, run = run_with_a_chart
    stash = run.reset_chart_artefacts(stash=True)
    for name in (f"{run.stem}.ti1", f"{run.stem}.ti2", f"{run.stem}_01.tif"):
        (run.dir / name).write_text("the NEW chart")
    run.settle_chart_stash(stash, built=True)

    assert (run.dir / f"{run.stem}.ti2").read_text() == "the NEW chart"
    assert not (run.dir / f"{run.stem}_02.tif").exists(), \
        "a page of the old chart survived beside the new one"
    assert not run.chart_stash_dirs()


def test_a_stash_never_puts_a_file_back_over_a_newer_one(run_with_a_chart):
    """The repair on reopen cannot know how the build ended, so it must be safe
    either way: a file is only put back when the run does not already have one
    of that name."""
    proj, run = run_with_a_chart
    run.reset_chart_artefacts(stash=True)
    (run.dir / f"{run.stem}.ti2").write_text("the NEW chart")   # the build DID finish

    again = Project.load(proj.root).all_runs()[0]
    assert (again.dir / f"{run.stem}.ti2").read_text() == "the NEW chart"
    assert not again.chart_stash_dirs()


def test_without_the_stash_the_old_behaviour_is_unchanged(run_with_a_chart):
    """`stash=False` is still a plain wipe — every existing caller and every
    existing test depends on that."""
    _proj, run = run_with_a_chart
    assert run.reset_chart_artefacts() is None
    assert _files(run) == ["meta.json"]
    assert not run.chart_stash_dirs()


def test_setting_a_chart_aside_does_not_spawn_an_old_folder(run_with_a_chart):
    """A run with no measurement has nothing to archive, and Knut's rule is that
    it must not grow an `old/` folder just for iterating on a chart."""
    _proj, run = run_with_a_chart
    run.reset_chart_artefacts(stash=True)
    assert not (run.dir / "old").exists()
