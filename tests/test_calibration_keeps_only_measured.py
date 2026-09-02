"""Option 3: a calibration chart is kept only if it was measured.

The owner ruled this on 2026-09-02, in writing, in
``RULING-calibration-old-charts.txt``, against a recommendation to keep the last
replaced chart instead:

> **OPTION 3 — Keep it only if it was measured; experiments leave nothing.**
> This matches what profile runs already do. A chart you never measured is
> treated as an experiment and disappears when you replace it; a chart that was
> measured is always kept.

It is also what K6 had already asked for — ``docs/design/per_run_description.md``
line 400, Knut at beta.148: *"`cal/old/<date>/` holds only what cannot be
regenerated … The chart is replaced, as a run's is."*

**"Experiments leave nothing" is not "delete it now".** Nothing in ``cal/`` is
"regenerated" unless the build finishes, and a build can fail, be stopped, or be
killed with the app. So the chart is set aside in a hidden stash first and
dropped only once a replacement really exists — the same mechanism a profile run
has used since ``93ba45ee``, through the same code. A dropped stash is a
deliberate discard the owner has ruled on; a stash dropped when the build FAILED
would be a bug, and the tests below are most of this file.

This file replaces ``test_calibration_keeps_its_promise.py``, which pinned the
Option 1 behaviour (every replacement archived) that the ruling overrules. Every
one of its measured-branch rows is kept here unchanged, because the ruling did
not touch that branch.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from core.file_manager import (
    STASH_SUPERSEDED,
    Calibration,
    CalibrationReset,
    files_matching,
)


CHART_NAMES = ("{s}.ti1", "{s}.ti2", "{s}.channels.json",
               "{s}_01.tif", "{s}_02.tif")
RESULT_NAMES = ("{s}.ti3", "{s}.cal")


def _make(root, *, measured: bool, exports: bool = True) -> Calibration:
    root.mkdir(parents=True, exist_ok=True)
    c = Calibration(root)
    c.ensure_dir()
    names = [n.format(s=c.stem) for n in CHART_NAMES]
    if measured:
        names += [n.format(s=c.stem) for n in RESULT_NAMES]
    for n in names:
        (c.dir / n).write_text(f"CONTENT OF {n}", encoding="utf-8")
    meta = c.load_meta()
    meta.description = "Canson Baryta, new ink set"
    c.save_meta(meta)
    if exports:
        c.ensure_exports_dir()
        (c.exports_dir / f"{c.stem}-colours.txt").write_text(
            "the hand-off sidecar", encoding="utf-8")
    return c


@pytest.fixture
def unmeasured(tmp_path):
    return _make(tmp_path / "MyProj", measured=False)


@pytest.fixture
def measured(tmp_path):
    return _make(tmp_path / "MyProj", measured=True)


def _one_archive(cal: Calibration):
    archives = sorted(cal.old_dir.iterdir())
    assert len(archives) == 1, f"expected one archive, got {archives}"
    return archives[0]


def _one_stash(cal: Calibration):
    stashes = cal.chart_stash_dirs()
    assert len(stashes) == 1, f"expected one stash, got {stashes}"
    return stashes[0]


# --------------------------------------------------------------------------
# 1. The ruling, stated as behaviour.
# --------------------------------------------------------------------------

def test_an_unmeasured_chart_leaves_nothing_behind(unmeasured):
    """"…disappears when you replace it." Ten Generate presses while iterating
    on a layout must leave zero dated folders, not ten."""
    cal = unmeasured
    assert len(cal.live_files()) == 5, "the fixture must hold a whole chart"

    cal.reset(stash=True)
    cal.settle_chart_stash(_one_stash(cal), built=True)

    assert cal.live_files() == [], "the folder was not cleared for the new chart"
    assert not cal.old_dir.exists(), (
        "an experiment left a dated folder behind, which is Option 1")
    assert cal.chart_stash_dirs() == [], "the stash outlived the build"


def test_a_measured_calibration_is_always_kept(measured):
    """The other half of the same sentence, and the branch the ruling did NOT
    touch: the chart, its measurement and the .cal all move to cal/old."""
    cal = measured
    cal.reset(stash=True)

    archive = _one_archive(cal)
    for n in RESULT_NAMES:
        name = n.format(s=cal.stem)
        assert (archive / name).is_file(), f"{name} lost from the archive"
    for n in CHART_NAMES:
        name = n.format(s=cal.stem)
        assert (archive / cal.ARCHIVE_CHART_DIRNAME / name).is_file(), (
            f"{name} was destroyed on the measured branch")
    assert cal.chart_stash_dirs() == [], (
        "a measured calibration must not be stashed — it is archived, and an "
        "archive survives a failed build while a stash does not")


def test_the_two_branches_cannot_both_run(measured):
    """A calibration is archived or discarded, never both. If `reset` ever
    archived AND stashed, settling the stash would drop files that are in the
    archive, or restore files the archive already holds."""
    got = measured.reset(stash=True)
    assert got.archive is not None and got.stash is None
    got2 = _make(measured.dir.parent.parent / "Other", measured=False).reset(
        stash=True)
    assert got2.archive is None and got2.stash is not None


# --------------------------------------------------------------------------
# 2. What "measured" means, and the boundary that decides somebody's afternoon.
# --------------------------------------------------------------------------
#
# The predicate is `Calibration.result_files()`: any live file in `cal/` whose
# suffix is .ti3 / .cal / .icc / .icm, or whose name ends `.ti3.engine-partial`.
# It is deliberately a question about EXISTENCE, not about content. Reading a
# .ti3 to judge whether it is "really" a measurement would put a parser between
# somebody's afternoon and the bin, and every way that parser can be wrong
# destroys work. Being wrong the other way costs a folder.

def test_an_empty_ti3_still_counts_as_measured(tmp_path):
    """Zero bytes. chartread writes the .ti3 only on a clean exit, so a 0-byte
    one is odd — and it is still not ours to judge."""
    cal = _make(tmp_path / "P", measured=False)
    (cal.dir / f"{cal.stem}.ti3").write_text("", encoding="utf-8")
    cal.reset(stash=True)
    assert cal.old_dir.exists(), "an empty .ti3 was treated as no measurement"
    assert (_one_archive(cal) / f"{cal.stem}.ti3").is_file()


def test_a_truncated_ti3_still_counts_as_measured(tmp_path):
    """A file that stops mid-record. It parses as nothing and it is still the
    only trace of a reading somebody took."""
    cal = _make(tmp_path / "P", measured=False)
    (cal.dir / f"{cal.stem}.ti3").write_text(
        "CTI3\n\nNUMBER_OF_SETS 240\nBEGIN_DATA\n1 100.0 0.0 0",
        encoding="utf-8")
    cal.reset(stash=True)
    assert (_one_archive(cal) / f"{cal.stem}.ti3").is_file(), (
        "a half-written measurement was thrown away as an experiment")


def test_an_abandoned_reading_counts_as_measured(tmp_path):
    """`<stem>.ti3.engine-partial` is exactly what a measurement stopped part
    way through leaves behind. Its SUFFIX is `.engine-partial`, so a rule based
    on suffixes alone would miss it — `result_files()` names it."""
    cal = _make(tmp_path / "P", measured=False)
    partial = cal.dir / f"{cal.stem}.ti3.engine-partial"
    partial.write_text("CTI3 partial\n", encoding="utf-8")
    cal.reset(stash=True)
    assert (_one_archive(cal) / partial.name).is_file(), (
        "the abandoned reading was treated as an experiment and dropped")


def test_a_profile_built_from_the_calibration_counts_as_measured(tmp_path):
    """An .icc in cal/ cannot exist without a measurement having happened, even
    if the .ti3 has since been moved away."""
    cal = _make(tmp_path / "P", measured=False)
    (cal.dir / f"{cal.stem}.icc").write_bytes(b"\x00ICC")
    cal.reset(stash=True)
    assert (_one_archive(cal) / f"{cal.stem}.icc").is_file()


def test_a_chart_and_nothing_else_is_an_experiment(unmeasured):
    """The whole of the other side: every file is a chart file, so nothing is
    kept. This is the fixture five files wide, and it is the common case."""
    assert unmeasured.result_files() == []
    assert len(unmeasured.chart_files()) == 5
    unmeasured.reset(stash=True)
    assert not unmeasured.old_dir.exists()


def test_the_window_can_only_ever_promise_less_than_the_code_keeps(tmp_path):
    """THE TWO PREDICATES ARE NOT THE SAME, and the direction matters.

    The window asks `cal.ti3.exists() or cal.cal_path.exists()` — which is
    `Calibration.exists()`, and the row in `calibration_run_type_plan.md`
    Table C. The code asks `result_files()`, which is wider. So a state the
    window calls "not measured" may still be one the code keeps (an
    engine-partial, a bare .icc), but a state the window calls MEASURED is
    always one the code keeps.

    That is the only safe direction: the window can under-promise and leave an
    unexpected folder; it can never promise safety over a discard. Checked
    exhaustively over every combination of the four result kinds."""
    kinds = [".ti3", ".cal", ".icc", ".ti3.engine-partial"]
    for mask in range(1 << len(kinds)):
        root = tmp_path / f"P{mask}"
        cal = _make(root, measured=False, exports=False)
        for i, tail in enumerate(kinds):
            if mask & (1 << i):
                (cal.dir / f"{cal.stem}{tail}").write_text("x", encoding="utf-8")
        window_says_measured = cal.exists()
        code_keeps = bool(cal.result_files())
        assert not (window_says_measured and not code_keeps), (
            f"the window would promise the chart is kept and the code would "
            f"drop it: {[k for i, k in enumerate(kinds) if mask & (1 << i)]}")


# --------------------------------------------------------------------------
# 3. The stash: nothing is lost when the build does not finish.
# --------------------------------------------------------------------------

def test_the_chart_is_set_aside_before_the_build_not_deleted(unmeasured):
    """Between `reset()` and the end of the build the chart must still exist
    somewhere, byte for byte. This is the whole reason the stash is here."""
    cal = unmeasured
    before = {p.name: p.read_text(encoding="utf-8") for p in cal.live_files()}

    got = cal.reset(stash=True)

    assert got.stash is not None and got.stash.is_dir()
    assert cal.live_files() == [], "cal/ was not cleared for the new chart"
    for name, content in before.items():
        assert (got.stash / name).read_text(encoding="utf-8") == content, (
            f"{name} was destroyed before the build had produced anything")


def test_a_failed_build_puts_every_byte_back(unmeasured):
    """The bug this guards is the one that would make the ruling unshippable:
    the chart dropped for an experiment that never got its replacement."""
    cal = unmeasured
    before = {p.name: p.read_text(encoding="utf-8") for p in cal.live_files()}
    sidecar = (cal.exports_dir / f"{cal.stem}-colours.txt").read_text(
        encoding="utf-8")

    stash = cal.reset(stash=True).stash
    cal.settle_chart_stash(stash, built=False)

    after = {p.name: p.read_text(encoding="utf-8") for p in cal.live_files()}
    assert after == before, "a build that produced nothing lost the old chart"
    assert (cal.exports_dir / f"{cal.stem}-colours.txt").read_text(
        encoding="utf-8") == sidecar, "the sidecars did not come back"
    assert cal.chart_stash_dirs() == []


def test_a_failed_build_leaves_none_of_its_own_rubbish(unmeasured):
    """A dead build still writes files. Restoring only the stash used to let
    those leftovers win — raise the page count, press Stop, and the folder kept
    a page the chart never had."""
    cal = unmeasured
    stash = cal.reset(stash=True).stash
    # what a build that then died wrote:
    (cal.dir / f"{cal.stem}.ti1").write_text("half a chart", encoding="utf-8")
    (cal.dir / f"{cal.stem}_03.tif").write_text("a page the old chart never had",
                                                encoding="utf-8")
    cal.ensure_exports_dir()
    (cal.exports_dir / "new-sidecar.txt").write_text("from the dead build",
                                                     encoding="utf-8")

    cal.settle_chart_stash(stash, built=False)

    assert not (cal.dir / f"{cal.stem}_03.tif").exists(), (
        "a page from the unfinished build survived the restore")
    assert (cal.dir / f"{cal.stem}.ti1").read_text(encoding="utf-8") == (
        f"CONTENT OF {cal.stem}.ti1"), "the leftover .ti1 won over the original"
    assert not (cal.exports_dir / "new-sidecar.txt").exists(), (
        "the dead build's exports/ survived, mixed in with the restored one")


def test_a_finished_build_drops_the_stash(unmeasured):
    cal = unmeasured
    stash = cal.reset(stash=True).stash
    (cal.dir / f"{cal.stem}.ti2").write_text("the new chart", encoding="utf-8")

    cal.settle_chart_stash(stash, built=True)

    assert not stash.exists()
    assert cal.chart_stash_dirs() == []
    assert (cal.dir / f"{cal.stem}.ti2").read_text(
        encoding="utf-8") == "the new chart"
    assert not cal.old_dir.exists()


def test_an_empty_stash_takes_nothing_with_it(unmeasured):
    """An empty stash represents nothing and must therefore TAKE nothing. The
    sweep below a restore removes every chart file that is not in the stash; on
    an empty one that is all of them, and there is nothing to put back."""
    from core.file_manager import make_chart_stash

    cal = unmeasured
    stash = make_chart_stash(cal.dir)
    before = {p.name: p.read_text(encoding="utf-8") for p in cal.live_files()}

    cal.settle_chart_stash(stash, built=False)

    after = {p.name: p.read_text(encoding="utf-8") for p in cal.live_files()}
    assert after == before, "an empty stash swept the folder it belonged to"


def test_without_a_stash_the_chart_simply_goes(unmeasured):
    """`stash=False` is the plain form. It is what a caller that is not running
    a build gets, and it must not leave a hidden folder behind."""
    cal = unmeasured
    got = cal.reset()
    assert got == CalibrationReset(None, None)
    assert cal.live_files() == []
    assert cal.chart_stash_dirs() == []
    assert not cal.exports_dir.exists()
    assert not cal.old_dir.exists()


def test_opening_the_project_settles_a_stash_a_dead_process_left(tmp_path):
    """A build interrupted by the app CLOSING never reaches the settle, and
    closing the window is exactly what a person does when a build is taking too
    long. `Project.load` finishes the job on the next open — for `cal/` as it
    already did for a run."""
    from core.file_manager import Project

    proj = Project.create(tmp_path / "P", "P")
    cal = _make(proj.root, measured=False)
    before = {p.name: p.read_text(encoding="utf-8") for p in cal.live_files()}
    cal.reset(stash=True)                    # …and then the process dies

    reopened = Project.load(proj.root)

    cal2 = reopened.calibration
    assert cal2.chart_stash_dirs() == [], "the stash was left in cal/ for ever"
    after = {p.name: p.read_text(encoding="utf-8") for p in cal2.live_files()}
    assert after == before, (
        "the app was killed mid-build and the calibration chart did not come "
        "back — the user has neither chart")


def test_a_superseded_stash_is_dropped_and_not_restored(tmp_path):
    """The one exception, marked inside the stash itself: a build that DID
    finish but whose stash could not be removed. Putting it back would overwrite
    the chart that was really built."""
    from core.file_manager import Project

    proj = Project.create(tmp_path / "P", "P")
    cal = _make(proj.root, measured=False)
    stash = cal.reset(stash=True).stash
    (stash / STASH_SUPERSEDED).write_text("", encoding="utf-8")
    (cal.dir / f"{cal.stem}.ti2").write_text("the chart that WAS built",
                                             encoding="utf-8")

    reopened = Project.load(proj.root)

    assert reopened.calibration.chart_stash_dirs() == []
    assert (cal.dir / f"{cal.stem}.ti2").read_text(
        encoding="utf-8") == "the chart that WAS built"


def test_the_stash_is_not_mistaken_for_the_calibration(unmeasured):
    """`live_files()` and `chart_files()` must not see into the stash, or a
    second Generate press would stash the stash."""
    cal = unmeasured
    cal.reset(stash=True)
    assert cal.live_files() == []
    assert cal.chart_files() == []
    assert cal.result_files() == []


# --------------------------------------------------------------------------
# 4. cal/exports/ — it goes wherever the chart goes, and never on its own.
# --------------------------------------------------------------------------

def test_the_sidecars_die_with_the_chart_they_describe(unmeasured):
    """`-colours.txt` and the i1Profiler pair are rebuilt from one particular
    chart. Kept after that chart is gone they are a hand-off nobody can
    reproduce, which is the "reads like something usable and is not" fault Knut
    objected to at beta.148 — one level down."""
    cal = unmeasured
    stash = cal.reset(stash=True).stash
    assert (stash / "exports" / f"{cal.stem}-colours.txt").is_file(), (
        "the sidecars were deleted outright, so a failed build loses them")
    cal.settle_chart_stash(stash, built=True)
    assert not cal.exports_dir.exists()


def test_the_sidecars_travel_into_the_archive_when_it_was_measured(measured):
    """The measured branch is unchanged: they are files the user may already
    have handed to someone else, and the archive is where they belong."""
    measured.reset(stash=True)
    sidecar = (_one_archive(measured) / measured.ARCHIVE_CHART_DIRNAME
               / "exports" / f"{measured.stem}-colours.txt")
    assert sidecar.is_file(), "the exports sidecars were deleted"
    assert sidecar.read_text(encoding="utf-8") == "the hand-off sidecar"


# --------------------------------------------------------------------------
# 5. The measured branch, unchanged — every row from the file this replaces.
# --------------------------------------------------------------------------

def test_the_dated_folders_own_listing_still_holds_only_results(measured):
    """K6 / T5.13, `docs/design/per_run_description.md:400`. The compromise the
    previous fix reached is not this ruling's to disturb."""
    cal = measured
    cal.reset(stash=True)
    archive = _one_archive(cal)
    loose = sorted(p.name for p in archive.iterdir() if p.is_file())
    assert loose == sorted([f"{cal.stem}.cal", f"{cal.stem}.ti3", "meta.json"]), (
        f"the dated folder's own listing changed: {loose}")


def test_the_stored_chart_copy_is_still_left_alone(measured):
    """`cal/chart/` is what Restore Used Chart reads; T5.13 says a rebuild must
    not move it."""
    cal = measured
    cal.snapshot_dir.mkdir()
    (cal.snapshot_dir / f"{cal.stem}.ti2").write_text("the measured chart",
                                                      encoding="utf-8")
    cal.reset(stash=True)
    assert (cal.snapshot_dir / f"{cal.stem}.ti2").read_text(
        encoding="utf-8") == "the measured chart"


def test_the_stored_chart_copy_survives_an_experiment_too(unmeasured):
    """…and the discard branch must not touch it either. `cal/chart/` is a
    FOLDER, and the discard walks `chart_files()`, which is files only."""
    cal = unmeasured
    cal.snapshot_dir.mkdir()
    (cal.snapshot_dir / f"{cal.stem}.ti2").write_text("the measured chart",
                                                      encoding="utf-8")
    stash = cal.reset(stash=True).stash
    cal.settle_chart_stash(stash, built=True)
    assert (cal.snapshot_dir / f"{cal.stem}.ti2").read_text(
        encoding="utf-8") == "the measured chart"


def test_a_calibration_with_nothing_in_it_does_nothing(tmp_path):
    cal = Calibration(tmp_path / "Empty")
    (tmp_path / "Empty").mkdir()
    cal.ensure_dir()
    assert cal.reset(stash=True) == CalibrationReset(None, None)
    assert not cal.old_dir.exists()
    assert cal.chart_stash_dirs() == [], (
        "an empty calibration made a stash, so every Generate press on a fresh "
        "project would leave a hidden folder")


def test_two_measured_rebuilds_in_one_day_keep_two_separate_charts(tmp_path):
    cal = _make(tmp_path / "MyProj", measured=True)
    first = {p.name: p.read_text(encoding="utf-8") for p in cal.chart_files()}
    cal.reset(stash=True)
    for n in CHART_NAMES + RESULT_NAMES:
        (cal.dir / n.format(s=cal.stem)).write_text("the SECOND chart",
                                                    encoding="utf-8")
    cal.reset(stash=True)

    archives = sorted(cal.old_dir.iterdir())
    assert len(archives) == 2, f"the second rebuild merged into the first: {archives}"
    a1 = archives[0] / cal.ARCHIVE_CHART_DIRNAME
    a2 = archives[1] / cal.ARCHIVE_CHART_DIRNAME
    for name, content in first.items():
        assert (a1 / name).read_text(encoding="utf-8") == content, (
            "the first chart was overwritten by the second")
    for n in CHART_NAMES:
        assert (a2 / n.format(s=cal.stem)).read_text(
            encoding="utf-8") == "the SECOND chart"


def test_two_archives_in_the_same_second_do_not_share_a_folder(tmp_path):
    """The stamp carries the time, so a same-day collision is impossible; a
    same-SECOND one is not, and a shared folder would silently overwrite."""
    cal = _make(tmp_path / "MyProj", measured=False, exports=False)
    when = datetime(2026, 9, 2, 16, 20, 38)
    first = cal.archive_to_old(when, only=[], chart=cal.chart_files())
    for n in CHART_NAMES:
        (cal.dir / n.format(s=cal.stem)).write_text("the SECOND chart",
                                                    encoding="utf-8")
    second = cal.archive_to_old(when, only=[], chart=cal.chart_files())
    assert first != second, "two archives landed in one folder"
    assert first.name == "2026-09-02_162038"
    assert second.name == "2026-09-02_162038_2"
    assert (first / cal.ARCHIVE_CHART_DIRNAME
            / f"{cal.stem}.ti2").read_text(encoding="utf-8") != "the SECOND chart"


def test_an_archive_is_never_swept_into_the_next_one(tmp_path):
    cal = _make(tmp_path / "MyProj", measured=True)
    cal.reset(stash=True)
    for n in CHART_NAMES + RESULT_NAMES:
        (cal.dir / n.format(s=cal.stem)).write_text("second", encoding="utf-8")
    cal.reset(stash=True)
    for archive in cal.old_dir.iterdir():
        assert not (archive / "old").exists(), "old/ nested inside old/"
        assert not (archive / cal.ARCHIVE_CHART_DIRNAME / "old").exists()


def test_the_archived_chart_is_openable_as_a_chart(measured):
    """The app's "Open Chart File (.ti2)" finds a chart's pages with
    `files_matching(ti2.parent, f"{stem}*.tif")` (`TabMeasure._try_load_tiffs`).
    So the archived `.ti2` is only openable if its page images are in the SAME
    folder — which is why the chart moves as a whole and not file by file."""
    cal = measured
    cal.reset(stash=True)
    kept = _one_archive(cal) / cal.ARCHIVE_CHART_DIRNAME
    ti2 = kept / f"{cal.stem}.ti2"
    assert ti2.is_file()
    pages = files_matching(ti2.parent, f"{cal.stem}*.tif")
    assert len(pages) == 2, (
        f"the pages did not travel with the .ti2 they belong to: {pages}")


def test_the_calibrations_own_words_survive_either_branch(tmp_path):
    """K3, Knut beta.147. `meta.json` describes the calibration slot, which
    outlives both the chart and the discard."""
    for is_measured in (True, False):
        cal = _make(tmp_path / f"P{is_measured}", measured=is_measured)
        stash = cal.reset(stash=True).stash
        cal.settle_chart_stash(stash, built=True)
        assert cal.load_meta().description == "Canson Baryta, new ink set", (
            f"the description was lost (measured={is_measured})")


# --------------------------------------------------------------------------
# 6. The build path really uses this, rather than something beside it.
# --------------------------------------------------------------------------

def test_the_build_sets_the_calibration_chart_aside(tmp_path):
    """A test on `Calibration` alone proves nothing about the app. The fault
    this whole thread is about lived in the CALL SITE."""
    import inspect

    from workflow.chart_creator import ChartCreator

    src = inspect.getsource(ChartCreator.generate)
    i = src.index("cal_target")
    branch = src[i:src.index("else:", i)]
    assert "reset(stash=True)" in branch, (
        "the calibration build no longer sets the old chart aside, so a build "
        "that fails leaves cal/ with no chart at all")
    assert ".stash" in branch, "the stash is created and then not held on to"


def test_every_ending_settles_the_calibration_stash():
    """`_finish` is the ONE exit every ending funnels through. It must not
    branch on which slot owns the stash, or one of them will be forgotten."""
    import inspect

    from workflow.chart_creator import ChartCreator

    src = inspect.getsource(ChartCreator._finish)
    assert "owner.settle_chart_stash(stash, built=bool(tiffs))" in src, (
        "the finish handler no longer settles the stash for both slots")


def test_a_run_and_a_calibration_settle_through_the_same_code():
    """One mechanism, not two. Two would drift, and the drift would be
    somebody's chart."""
    import inspect

    from core.file_manager import Calibration as C
    from core.file_manager import Run

    for owner in (Run, C):
        src = inspect.getsource(owner.settle_chart_stash)
        assert "settle_chart_stash(self.dir, stash, built=built" in src, (
            f"{owner.__name__} has grown its own settle implementation")


# --------------------------------------------------------------------------
# 7. THE WINDOW AND THE CODE NOW DISAGREE, AND THAT IS DELIBERATE AND MARKED.
# --------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason=(
    "M-CAL-REPLACE-CHART still promises the unmeasured chart is kept, and "
    "since the owner's option-3 ruling of 2026-09-02 it is not. The wording is "
    "his to approve, so it is PROPOSED in the hand-back report and NOT written "
    "into the tab. THIS BRANCH MUST NOT BE MERGED OR TAGGED WHILE THIS TEST "
    "XFAILS: the window would be lying, which is the exact fault the ruling "
    "came out of. When the new wording is approved and landed, this test goes "
    "green and `strict=True` turns the gate RED until the marker is removed — "
    "so the pair cannot drift again in either direction."))
def test_the_window_says_what_the_code_does():
    """The pair that drifted, checked in the only way that survives a rewording:
    against the BEHAVIOUR, not against a quoted sentence.

    The unmeasured window must not tell the user the chart moves to "cal/old",
    because it no longer does. It must say something a beginner can tell apart
    from the measured window, which still does move everything there."""
    import inspect

    from ui.tabs.tab_chart import TabChart

    src = inspect.getsource(TabChart._confirm_replacing_calibration)
    unmeasured_branch = src[src.index("else:", src.index("go = tr(")):]
    assert "cal/old" not in unmeasured_branch, (
        "the window still tells the user an unmeasured chart moves to "
        "“cal/old”, and it is dropped instead")
    assert "Nothing is deleted" not in unmeasured_branch, (
        "the window still says nothing is deleted over a chart that is")


def test_the_measured_window_still_promises_correctly():
    """The other window did NOT change and must not: everything it names really
    does move to cal/old. If the reword above touches this branch by accident,
    this fails."""
    import inspect

    from ui.tabs.tab_chart import TabChart

    src = inspect.getsource(TabChart._confirm_replacing_calibration)
    measured_branch = src[src.index("if measured:"):src.index("go = tr(")]
    assert "cal/old" in measured_branch
    assert "the calibration chart" in measured_branch, (
        "M-CAL-REPLACE-MEASURED no longer lists the chart among what moves")


def test_the_window_and_the_code_ask_the_same_kind_of_question():
    """Both predicates live in `Calibration`, so the divergence is at least
    visible in one place. The window asks `exists()`; the code asks
    `result_files()`. If the window's line is ever rewritten to something that
    is NOT `Calibration.exists()`, this fails and the direction has to be
    re-checked by hand (see the exhaustive test in section 2)."""
    import inspect

    from ui.tabs.tab_chart import TabChart

    src = inspect.getsource(TabChart._confirm_replacing_calibration)
    assert "measured = cal.ti3.exists() or cal.cal_path.exists()" in src, (
        "the window's definition of “measured” has changed; check it is "
        "still narrower than Calibration.result_files(), or the window can "
        "promise safety over a chart the code drops")


@pytest.mark.xfail(strict=True, reason=(
    "The file guide's `cal/old/` entry says a new calibration chart moves "
    "“what was there” into a dated folder. Since the option-3 ruling that is "
    "true only when something was measured. Same approval route as the window "
    "above, same batch, same rule: NOT rewritten here. This is the “where are "
    "my files?” page, so it is guarded rather than only mentioned."))
def test_the_file_guide_says_what_the_code_does():
    entry = _cal_old_guide_text()
    assert "Earlier calibrations" in entry, (
        "precondition: this is not the cal/old row any more")
    assert "what was there" not in entry, (
        "the file guide still says everything moves to cal/old")


def _cal_old_guide_text() -> str:
    """The `cal/old/` row of the file guide, whichever function builds it."""
    import inspect

    import ui.file_guide as fg

    src = inspect.getsource(fg)
    i = src.index('("cal/old/"')
    return src[i:src.index("\n", i)]


# --------------------------------------------------------------------------
# 8. What the adversarial round of 2026-09-02 found in the code this touches.
# --------------------------------------------------------------------------

def test_an_empty_exports_folder_is_not_a_calibration(tmp_path):
    """T2-E. `cal/exports/` was appended whenever the DIRECTORY existed, so a
    `cal/` holding nothing but the empty folder the app itself makes produced a
    whole dated archive of nothing — and `reset()`'s "None when cal/ held
    nothing" was false. The line that proves it is `ensure_exports_dir()`; the
    old test never called it, which is why it could not fail."""
    cal = Calibration(tmp_path / "Empty")
    (tmp_path / "Empty").mkdir()
    cal.ensure_dir()
    cal.ensure_exports_dir()          # <- the app's own call, and the mutation

    assert cal.reset(stash=True) == CalibrationReset(None, None)
    assert not cal.old_dir.exists(), "an archive of nothing was made"
    assert cal.chart_stash_dirs() == []
    assert cal.exports_dir.is_dir(), (
        "an exports/ folder with no chart beside it was removed — it is the "
        "user's, and nothing is being replaced")


def test_orphan_sidecars_with_no_chart_are_left_alone(tmp_path):
    """The same rule with content in it. Sidecars describe a chart; with no
    chart and no result there is nothing being replaced, so they stay."""
    cal = Calibration(tmp_path / "Orphan")
    (tmp_path / "Orphan").mkdir()
    cal.ensure_dir()
    cal.ensure_exports_dir()
    (cal.exports_dir / "handed-to-a-customer.txt").write_text(
        "sent last week", encoding="utf-8")

    cal.reset(stash=True)

    assert (cal.exports_dir / "handed-to-a-customer.txt").read_text(
        encoding="utf-8") == "sent last week"


def test_a_file_the_os_will_not_release_is_never_in_two_places(tmp_path,
                                                               monkeypatch):
    """T2-D. `shutil.move` falls back to copy-then-unlink when the rename
    fails, so a locked file ended up copied INTO the archive and still live —
    a chart in two places, and an archive with a hole in it while the window
    said it was whole."""
    import shutil as _shutil

    from core import file_manager as fm

    cal = _make(tmp_path / "Locked", measured=True, exports=False)
    stuck = cal.dir / f"{cal.stem}_02.tif"
    real_move = _shutil.move

    def _move(src, dst):
        if Path(src).name == stuck.name:
            _shutil.copy2(src, dst)          # the copy half succeeds…
            raise PermissionError(1, "Operation not permitted", str(src))
        return real_move(src, dst)

    monkeypatch.setattr(fm.shutil, "move", _move)
    cal.reset(stash=True)

    archive = _one_archive(cal)
    assert stuck.exists(), "the file the OS would not release was lost"
    assert not (archive / cal.ARCHIVE_CHART_DIRNAME / stuck.name).exists(), (
        "the same file is live AND in the archive: the chart is in two places "
        "and neither copy is the whole chart")


def test_a_cal_folder_that_cannot_be_written_does_not_raise(tmp_path,
                                                            monkeypatch):
    """T2-D. `reset()` runs inside a Qt slot with no `except` above it, so a
    read-only `cal/` put a PermissionError on screen as a crash. Failing here
    must leave cal/ exactly as it was and say so in the log."""
    from core import file_manager as fm

    cal = _make(tmp_path / "ReadOnly", measured=True)
    before = {p.name: p.read_text(encoding="utf-8") for p in cal.live_files()}

    def _boom(*a, **kw):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(fm.Calibration, "archive_to_old", _boom)
    got = cal.reset(stash=True)          # must not raise

    assert got == CalibrationReset(None, None)
    after = {p.name: p.read_text(encoding="utf-8") for p in cal.live_files()}
    assert after == before, "a failed archive still took the calibration apart"


def test_the_app_says_where_the_calibration_archive_went(tmp_path):
    """T2-A. `reset()` returned the archive folder and nobody read it, so the
    window promised "a folder named with today's date" and the app never named
    it anywhere. The SENTENCE is the owner's to approve; the folder reaching
    the log the user is watching is the mechanism, and it is wired."""
    import inspect

    from workflow.chart_creator import ChartCreator

    src = inspect.getsource(ChartCreator.generate)
    assert "_announce_calibration_archive(done.archive, on_line)" in src, (
        "the archive folder is thrown away again, so nobody can find it")

    lines: list[str] = []
    creator = ChartCreator.__new__(ChartCreator)
    creator._announce_calibration_archive(tmp_path / "cal" / "old" / "S",
                                          lines.append)
    assert lines and "old" in lines[0]
    lines.clear()
    creator._announce_calibration_archive(None, lines.append)
    assert lines == [], (
        "an unmeasured rebuild announced an archive that is not there")
