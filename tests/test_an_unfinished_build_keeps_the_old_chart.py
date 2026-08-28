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


def test_a_surviving_stash_always_means_the_build_never_finished(run_with_a_chart):
    """THE HEURISTIC THIS REPLACES WAS MEASURED WRONG ON SCREEN.

    It asked whether the run held a `.ti2` and a page image. printtarg writes
    the page at 0.28 s and the `.ti2` at 0.49 s of a 1.4 s build, so that was
    true for most of every build: killing ChromIQ mid-printtarg produced a run
    that "had a finished chart", the complete original was dropped, and the
    interrupted build's half a chart was kept.

    The exact signal costs nothing: every ending a build can have goes through
    `_finish`, which settles the stash and removes it. A stash that is still
    there belongs to a process that died, whatever the run happens to contain.
    """
    proj, run = run_with_a_chart
    before = {p.name: p.read_text() for p in run.dir.iterdir() if p.is_file()}
    run.reset_chart_artefacts(stash=True)
    # what a half-done printtarg looks like: the page and the .ti2 are there…
    (run.dir / f"{run.stem}.ti2").write_text("half of the new chart")
    (run.dir / f"{run.stem}_01.tif").write_text("half of the new page")

    again = Project.load(proj.root).all_runs()[0]
    after = {p.name: p.read_text() for p in again.dir.iterdir() if p.is_file()}
    assert after == before, "an interrupted build was mistaken for a finished one"
    assert not again.chart_stash_dirs()


def test_a_superseded_stash_is_dropped_not_restored(run_with_a_chart):
    """The one exception, and it is marked inside the stash rather than guessed:
    a build that really did finish but whose stash could not be removed."""
    proj, run = run_with_a_chart
    stash = run.reset_chart_artefacts(stash=True)
    (run.dir / f"{run.stem}.ti2").write_text("the NEW chart")
    (run.dir / f"{run.stem}_01.tif").write_text("the NEW page")
    (stash / run.STASH_SUPERSEDED).write_text("")

    again = Project.load(proj.root).all_runs()[0]
    assert (again.dir / f"{run.stem}.ti2").read_text() == "the NEW chart"
    assert not again.chart_stash_dirs()


def test_a_stopped_build_leaves_no_orphan_pages(run_with_a_chart):
    """Two clicks, one chart made of two builds. Measured on screen: build a
    one-page chart, raise the page count to three, press Generate, press Stop —
    and the run kept `_02.tif` and `_03.tif` for a one-page `.ti2`, because
    putting a chart back walked only the stash and a page the OLD chart never
    had is not in it."""
    proj, run = run_with_a_chart
    before = {p.name for p in run.dir.iterdir() if p.is_file()}
    stash = run.reset_chart_artefacts(stash=True)
    # the taller build gets further than the old one ever was
    (run.dir / f"{run.stem}.ti2").write_text("three pages")
    for n in ("_01", "_02", "_03"):
        (run.dir / f"{run.stem}{n}.tif").write_text("a page of the new chart")

    run.settle_chart_stash(stash, built=False)

    after = {p.name for p in run.dir.iterdir() if p.is_file()}
    assert after == before, f"orphans survived: {sorted(after - before)}"


def test_the_leftovers_of_an_unfinished_build_never_beat_the_original(
        run_with_a_chart):
    """THE FIX THAT WAS ITSELF THE BUG. The first version skipped a stashed file
    whenever something of that name existed, on the reasoning that a new chart
    should win. But a build that produced NO chart still leaves rubbish behind —
    a `.ti1` with no `.ti2`, a half-written page image — and those leftovers
    then won, so the original was destroyed with the stash.

    Measured on screen twice: Stop pressed during printtarg, and the app killed
    mid-build and reopened. Both times the `.ti2` came back and the page image
    did not, which is the data loss the stash exists to prevent, reached through
    the fix written to prevent it.
    """
    proj, run = run_with_a_chart
    before = {p.name: p.read_text() for p in run.dir.iterdir() if p.is_file()}
    stash = run.reset_chart_artefacts(stash=True)
    # what a stopped build leaves: a patch set and one page, and no .ti2
    (run.dir / f"{run.stem}.ti1").write_text("half-written by the dead build")
    (run.dir / f"{run.stem}_01.tif").write_text("a page nobody asked for")

    run.settle_chart_stash(stash, built=False)

    after = {p.name: p.read_text() for p in run.dir.iterdir() if p.is_file()}
    assert after == before, "the unfinished build's leftovers survived"


def test_the_same_holds_when_the_app_was_killed_and_reopened(run_with_a_chart):
    """The crash path, which is the one a person actually reaches: closing the
    window is how you escape a build."""
    proj, run = run_with_a_chart
    before = {p.name: p.read_text() for p in run.dir.iterdir() if p.is_file()}
    run.reset_chart_artefacts(stash=True)
    (run.dir / f"{run.stem}.ti1").write_text("half-written by the dead build")
    (run.dir / f"{run.stem}_01.tif").write_text("a page nobody asked for")
    # …and then the process dies, so nothing settles the stash.

    again = Project.load(proj.root).all_runs()[0]
    after = {p.name: p.read_text() for p in again.dir.iterdir() if p.is_file()}
    assert after == before, "the killed build's leftovers survived the reopen"
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


def test_an_empty_stash_takes_nothing_with_it(run_with_a_chart):
    """A RELEASE-BLOCKER FOUND ON SCREEN, and a regression in the fix above.

    The sweep removes every chart file that is not in the stash, on the grounds
    that it belongs to a build which produced no chart. With an EMPTY stash that
    is every chart file, and there is nothing to put back afterwards.

    An empty stash is reachable, not theoretical: `settle_chart_stash` catches a
    failed `rmtree`, logs it and carries on, so a successful restore can leave
    the emptied folder behind. Measured with a real Stop click and a real
    Argyll build: the chart was restored byte-for-byte, the log said "nothing is
    lost", and the next open left the run holding `meta.json` alone — the `.ti2`
    a printed sheet is read against among the casualties.
    """
    proj, run = run_with_a_chart
    before = {p.name: p.read_text() for p in run.dir.iterdir() if p.is_file()}
    empty = run.dir / f"{run.CHART_STASH_PREFIX}99999"
    empty.mkdir()

    run.settle_chart_stash(empty, built=False)

    after = {p.name: p.read_text() for p in run.dir.iterdir() if p.is_file()}
    assert after == before, "an empty stash destroyed the run's chart"
    assert not empty.exists(), "the empty stash was left behind to do it again"


def test_an_empty_stash_found_on_reopen_is_equally_harmless(run_with_a_chart):
    """The path it was actually measured on: the leftover is found by
    `Project.load`, not by the build that made it."""
    proj, run = run_with_a_chart
    before = {p.name: p.read_text() for p in run.dir.iterdir() if p.is_file()}
    (run.dir / f"{run.CHART_STASH_PREFIX}12345").mkdir()

    again = Project.load(proj.root).all_runs()[0]

    after = {p.name: p.read_text() for p in again.dir.iterdir() if p.is_file()}
    assert after == before
    assert not again.chart_stash_dirs()


def test_two_builds_in_one_session_do_not_share_a_stash(run_with_a_chart):
    """The name used to be the process id alone, so a second build reused the
    folder a previous one had left behind and merged into it — measured: two
    charts' files in one stash, and the previous build's bookkeeping marker
    restored into the run as a file."""
    _proj, run = run_with_a_chart
    first = run.reset_chart_artefacts(stash=True)
    (run.dir / f"{run.stem}.ti2").write_text("chart B")
    second = run.reset_chart_artefacts(stash=True)
    assert first != second, "the second build reused the first build's stash"
    assert first.is_dir() and second.is_dir()


def test_the_bookkeeping_marker_is_never_restored_into_the_run(run_with_a_chart):
    """`SUPERSEDED-by-a-finished-build` is ChromIQ talking to itself. It must
    never turn up in the person's run folder beside their chart."""
    _proj, run = run_with_a_chart
    stash = run.reset_chart_artefacts(stash=True)
    (stash / run.STASH_SUPERSEDED).write_text("")
    run.settle_chart_stash(stash, built=False)
    assert not (run.dir / run.STASH_SUPERSEDED).exists(), \
        "ChromIQ's own bookkeeping file was put in the run folder"
    assert (run.dir / f"{run.stem}.ti2").exists(), "…and the chart came back"


def test_a_stash_holding_only_the_marker_counts_as_empty(run_with_a_chart):
    """Otherwise the sweep would run with nothing to restore afterwards, which
    is the release-blocker above wearing a hat."""
    _proj, run = run_with_a_chart
    before = {p.name: p.read_text() for p in run.dir.iterdir() if p.is_file()}
    stash = run.dir / f"{run.CHART_STASH_PREFIX}77777"
    stash.mkdir()
    (stash / run.STASH_SUPERSEDED).write_text("")
    run.settle_chart_stash(stash, built=False)
    after = {p.name: p.read_text() for p in run.dir.iterdir() if p.is_file()}
    assert after == before
    assert not stash.exists()
