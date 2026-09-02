"""The calibration-replacement window promised an archive and the code deleted.

`TabChart._confirm_replacing_calibration` shows one of two windows immediately
before `Calibration.reset()` runs, and both of them say the chart is kept:

    M-CAL-REPLACE-CHART   (nothing measured yet)
        "Generating a new one replaces it. Nothing is deleted: the chart you
         have now moves to the project's “cal/old” folder, in a folder named
         with today's date, and you can go back to it at any time."

    M-CAL-REPLACE-MEASURED  (a finished calibration)
        "These move to the project's “cal/old” folder … nothing is deleted, and
         you can go back to them at any time:
           •  the calibration chart
           •  its measurement
           •  the calibration file (.cal) made from it"

Measured on master before the fix, an unmeasured calibration::

    BEFORE : MyProj-cal.channels.json  MyProj-cal.ti1  MyProj-cal.ti2
             MyProj-cal_01.tif  MyProj-cal_02.tif  meta.json
    cal.reset()
    AFTER  : meta.json
    cal/old exists: False

No measurement meant no results, so no archive was made at all and the chart was
unlinked — while the user was reading a sentence that told them it was safe, and
pressed the button because of it.

**The chart is kept in `cal/old/<date>/chart/`, one level down**, so Knut's
beta.148 narrowing still holds at the same time: the dated folder's own listing
carries only what cannot be regenerated (`docs/design/per_run_description.md`
K6/T5.13). Both of those tests live in `test_calibration_archive.py` and still
pass; this file guards the other half of the same promise.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from core.file_manager import Calibration, files_matching


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


# --------------------------------------------------------------------------
# 1. The reproduction, turned round.
# --------------------------------------------------------------------------

def test_an_unmeasured_chart_is_kept_rather_than_deleted(unmeasured):
    """The exact case that was measured on master: five files in, one out."""
    cal = unmeasured
    before = {p.name: p.read_text(encoding="utf-8") for p in cal.live_files()}
    assert len(before) == 5, "the fixture must hold a whole chart"

    cal.reset()

    kept = _one_archive(cal) / cal.ARCHIVE_CHART_DIRNAME
    assert kept.is_dir(), (
        "no chart folder in the archive — the window said the chart moves here")
    for name, content in before.items():
        assert (kept / name).is_file(), f"{name} was destroyed"
        assert (kept / name).read_text(encoding="utf-8") == content, (
            f"{name} is in the archive but its contents are not")


def test_the_archive_is_made_even_with_nothing_measured(unmeasured):
    """The one-line cause. `reset()` only archived when there were RESULTS, so
    an unmeasured calibration produced no `cal/old/` at all."""
    unmeasured.reset()
    assert unmeasured.old_dir.exists(), "cal/old was never created"


def test_the_measured_branch_keeps_the_chart_too(measured):
    """M-CAL-REPLACE-MEASURED names the chart FIRST of the three things that
    move. Only the other two were moving."""
    cal = measured
    archive_root = None
    cal.reset()
    archive_root = _one_archive(cal)
    for n in RESULT_NAMES:
        name = n.format(s=cal.stem)
        assert (archive_root / name).is_file(), f"{name} lost from the archive"
    for n in CHART_NAMES:
        name = n.format(s=cal.stem)
        assert (archive_root / cal.ARCHIVE_CHART_DIRNAME / name).is_file(), (
            f"{name} was destroyed on the measured branch")


def test_the_hand_off_sidecars_travel_with_the_chart(unmeasured):
    """`cal/exports/` was `rmtree`d, which made "Nothing is deleted" false a
    second time. These are files the user may already have sent somewhere."""
    unmeasured.reset()
    sidecar = (_one_archive(unmeasured) / unmeasured.ARCHIVE_CHART_DIRNAME
               / "exports" / f"{unmeasured.stem}-colours.txt")
    assert sidecar.is_file(), "the exports sidecars were deleted"
    assert sidecar.read_text(encoding="utf-8") == "the hand-off sidecar"


# --------------------------------------------------------------------------
# 2. …without breaking the rule the old behaviour was reaching for.
# --------------------------------------------------------------------------

def test_the_dated_folders_own_listing_still_holds_only_results(measured):
    """K6 / T5.13, `docs/design/per_run_description.md:400`. Knut's reason was
    that a dated folder holding a bare .ti1/.ti2 reads like a kept calibration
    and is not one. One level down, in a folder that says `chart`, keeps that
    true and keeps the chart."""
    cal = measured
    cal.reset()
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
    cal.reset()
    assert (cal.snapshot_dir / f"{cal.stem}.ti2").read_text(
        encoding="utf-8") == "the measured chart"


def test_the_folder_is_still_clear_for_the_new_chart(unmeasured):
    unmeasured.reset()
    assert unmeasured.live_files() == []
    assert not unmeasured.exports_dir.exists()


def test_a_calibration_with_nothing_in_it_spawns_no_archive(tmp_path):
    cal = Calibration(tmp_path / "Empty")
    (tmp_path / "Empty").mkdir()
    cal.ensure_dir()
    assert cal.reset() is None
    assert not cal.old_dir.exists()


# --------------------------------------------------------------------------
# 3. Two archives must never merge — that would be the same bug, one down.
# --------------------------------------------------------------------------

def test_two_rebuilds_in_one_day_keep_two_separate_charts(tmp_path):
    cal = _make(tmp_path / "MyProj", measured=False)
    first = {p.name: p.read_text(encoding="utf-8") for p in cal.live_files()}
    cal.reset()
    # …a second chart, generated later the same day.
    for n in CHART_NAMES:
        (cal.dir / n.format(s=cal.stem)).write_text("the SECOND chart",
                                                    encoding="utf-8")
    cal.reset()

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
    cal.reset()
    for n in CHART_NAMES + RESULT_NAMES:
        (cal.dir / n.format(s=cal.stem)).write_text("second", encoding="utf-8")
    cal.reset()
    for archive in cal.old_dir.iterdir():
        assert not (archive / "old").exists(), "old/ nested inside old/"
        assert not (archive / cal.ARCHIVE_CHART_DIRNAME / "old").exists()


# --------------------------------------------------------------------------
# 4. "…and you can go back to it at any time."
# --------------------------------------------------------------------------

def test_the_archived_chart_is_openable_as_a_chart(unmeasured):
    """The app's "Open Chart File (.ti2)" finds a chart's pages with
    `files_matching(ti2.parent, f"{stem}*.tif")` (`TabMeasure._try_load_tiffs`).
    So the archived `.ti2` is only openable if its page images are in the SAME
    folder — which is why the chart moves as a whole and not file by file."""
    cal = unmeasured
    cal.reset()
    kept = _one_archive(cal) / cal.ARCHIVE_CHART_DIRNAME
    ti2 = kept / f"{cal.stem}.ti2"
    assert ti2.is_file()
    pages = files_matching(ti2.parent, f"{cal.stem}*.tif")
    assert len(pages) == 2, (
        f"the pages did not travel with the .ti2 they belong to: {pages}")


# --------------------------------------------------------------------------
# 5. The window and the code, checked against each other.
# --------------------------------------------------------------------------

def test_the_window_still_says_what_the_code_now_does():
    """The pair that drifted. If either half is changed alone this fails, which
    is the only thing that stops the promise going false again.

    The text is approved (`docs/design/calibration_run_type_plan.md:237`) and is
    not this test's to change: it is quoted so a change to it is deliberate."""
    import inspect

    from ui.tabs.tab_chart import TabChart

    src = inspect.getsource(TabChart._confirm_replacing_calibration)
    promise = (
        '"Generating a new one replaces it. Nothing is deleted: the "\n'
        '                "chart you have now moves to the project\'s \\u201ccal/old\\u201d "\n'
        '                "folder, in a folder named with today\'s date, and you can go "\n'
        '                "back to it at any time."'
    )
    assert promise in src, (
        "M-CAL-REPLACE-CHART has changed. If that was deliberate and approved, "
        "check Calibration.reset() still does what the new words say, then "
        "update this test.")
    assert "the calibration chart" in src, (
        "M-CAL-REPLACE-MEASURED no longer lists the chart among what moves")
