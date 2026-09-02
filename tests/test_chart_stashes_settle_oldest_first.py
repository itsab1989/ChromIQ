"""Two orphaned chart stashes settle by AGE, so the newest chart survives.

WHAT WENT WRONG
    `chart_stash_dirs` promised "oldest first" and delivered `sorted()` on
    `.chart-stash-<pid>-<n>`, which orders by the pid AS A STRING:
    `.chart-stash-10000-0` sorts before `.chart-stash-9999-0` however old each
    one is, and the counter has no zero padding either, so `-10` sorts before
    `-9`.

    That order decides which chart a person keeps. `Project.load` settles the
    stashes in the order this function returns, and `settle_chart_stash` clears
    any file already sitting under a stashed name before putting the stashed one
    back — so the LAST stash processed is the chart that survives and the other
    is deleted, not archived. Two builds orphaned in two sessions therefore kept
    whichever chart happened to have the larger process id spelled first.

THE FIX
    Sort by `st_mtime`, with the name as a tie-break so the order is still
    stable for two stashes made in the same instant.

EVERY CASE HERE IS CHOSEN SO NAME ORDER AND AGE ORDER DISAGREE.
    That is the whole point: a case where the two agree cannot tell the fix
    from the fault. `test_a_tie_is_still_stable` is the one exception and says
    so — it guards the tie-break, which no ordering rule decides on its own.
"""
from __future__ import annotations

import os
from pathlib import Path

from core.file_manager import CHART_STASH_PREFIX, Calibration, chart_stash_dirs


def _stash(folder: Path, name: str, *, mtime: float, marker: str) -> Path:
    """A stash folder called *name*, holding one chart file, aged to *mtime*."""
    d = folder / f"{CHART_STASH_PREFIX}{name}"
    d.mkdir(parents=True)
    (d / "Demo-Project-cal.ti2").write_text(marker, encoding="utf-8")
    os.utime(d, (mtime, mtime))
    return d


def test_the_order_is_by_age_and_not_by_the_process_id(tmp_path):
    """`10000` spells before `9999` and is the NEWER build here, so name order
    and age order are opposites."""
    folder = tmp_path / "cal"
    folder.mkdir()
    _stash(folder, "10000-0", mtime=2_000_000.0, marker="NEW")
    _stash(folder, "9999-0", mtime=1_000_000.0, marker="OLD")

    order = [p.name for p in chart_stash_dirs(folder)]
    assert order == [f"{CHART_STASH_PREFIX}9999-0",
                     f"{CHART_STASH_PREFIX}10000-0"], (
        "the stashes came back in NAME order, so the newer build's chart is "
        f"restored first and the older one overwrites it: {order}")


def test_the_counter_is_not_compared_as_a_string_either(tmp_path):
    """`-10` is the newer build and spells before `-9`."""
    folder = tmp_path / "cal"
    folder.mkdir()
    _stash(folder, "555-10", mtime=2_000_000.0, marker="tenth")
    _stash(folder, "555-9", mtime=1_000_000.0, marker="ninth")

    order = [p.name for p in chart_stash_dirs(folder)]
    assert order == [f"{CHART_STASH_PREFIX}555-9",
                     f"{CHART_STASH_PREFIX}555-10"], order


def test_the_newest_chart_is_the_one_a_person_gets_back(tmp_path):
    """End to end through the calibration, exactly as `Project.load` does it."""
    root = tmp_path / "Demo-Project"
    root.mkdir()
    cal = Calibration(root)
    cal.ensure_dir()
    # the newer build's pid spells FIRST, so name order hands back the older
    # chart and it wins the last write
    _stash(cal.dir, "10000-0", mtime=2_000_000.0, marker="NEW")
    _stash(cal.dir, "9999-0", mtime=1_000_000.0, marker="OLD")

    for stash in cal.chart_stash_dirs():          # what Project.load does
        cal.settle_chart_stash(stash, built=False)

    assert (cal.dir / "Demo-Project-cal.ti2").read_text(encoding="utf-8") \
        == "NEW", "the older of the two orphaned charts won"
    assert cal.chart_stash_dirs() == []


def test_a_tie_is_still_stable(tmp_path):
    """Two stashes of the same age fall back to the name.

    This one CANNOT distinguish the fix from the fault — both orderings agree.
    It is here for the tie-break, which nothing else pins.
    """
    folder = tmp_path / "cal"
    folder.mkdir()
    _stash(folder, "1-1", mtime=5_000.0, marker="a")
    _stash(folder, "1-0", mtime=5_000.0, marker="b")

    order = [p.name for p in chart_stash_dirs(folder)]
    assert order == [f"{CHART_STASH_PREFIX}1-0",
                     f"{CHART_STASH_PREFIX}1-1"], order


def test_a_folder_that_is_not_there_holds_no_stashes(tmp_path):
    assert chart_stash_dirs(tmp_path / "not-here") == []
