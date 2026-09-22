"""B8-740: "Restore Used Chart" wrote over a run's meta.json with no archive.

`restore_slot` promises, in its own docstring, that a replaced side file is
archived into `old/` before the snapshot's copy is written. It was not, on the
two slots that matter: `live_files()` is suffix-filtered for a profiling run
and for a calibration (`PROFILING_CHART_SUFFIXES` holds no `meta.json`), so the
list of replaced side files was ALWAYS EMPTY there, while the copy loop still
overwrote the live file.

Measured by challenge round 36 on the real functions: a profiling run lost all
34 fields on that file and a calibration all 7, with no archive and no undo,
from one press of a button in the shipped UI. Among them the whole of a run's
frozen limit set, which is what `D20` exists to protect.

**This does not decide which fields belong to the chart.** That is a ruling and
it is Knut's: the snapshot rule was written in July for `editor_recipe` and the
printtarg knobs, and #182 later added seven compliance fields to the same file
without anyone revisiting what "restore the chart" should revert. What these
guards pin is the weaker thing that cannot be wrong either way -- **the loss is
recoverable**.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow import verify_chart_snapshot as VS


class _RunLikeSlot:
    """A profiling run's slot: `live_files` hides meta.json, as the real one does."""

    def __init__(self, live: Path, snap: Path) -> None:
        self.live_dir = live
        self.snapshot_dir = snap

    def live_files(self):
        return [p for p in self.live_dir.iterdir()
                if p.suffix in (".ti1", ".ti2", ".cht")]


def _slot(tmp_path: Path, live_meta: dict, snap_meta: dict) -> _RunLikeSlot:
    live = tmp_path / "runs" / "run1"
    live.mkdir(parents=True)
    (live / "meta.json").write_text(json.dumps(live_meta), encoding="utf-8")
    snap = live / "chart"
    snap.mkdir()
    (snap / "meta.json").write_text(json.dumps(snap_meta), encoding="utf-8")
    (snap / "chart.ti2").write_text("a chart", encoding="utf-8")
    return _RunLikeSlot(live, snap)


def _archived(live: Path) -> "dict | None":
    old = live / "old"
    if not old.exists():
        return None
    found = sorted(old.rglob("meta.json"))
    return json.loads(found[0].read_text(encoding="utf-8")) if found else None


def test_the_replaced_side_file_is_archived_before_it_is_overwritten(tmp_path):
    """MUTATION, proven to land: build the list from `live_files()` again and
    the archive is never written, because that list is filtered."""
    slot = _slot(tmp_path,
                 {"compliance_set_id": "chromiq_default",
                  "compliance_bound_at": "2026-09-01",
                  "description": "what the user has now"},
                 {"description": "what it was at measurement time"})
    VS.restore_slot(slot)
    kept = _archived(slot.live_dir)
    assert kept is not None, (
        "the live meta.json was overwritten with no archive, so a run's bound "
        "limit set is gone with no way back")
    assert kept["compliance_set_id"] == "chromiq_default"
    assert kept["compliance_bound_at"] == "2026-09-01"


def test_the_archive_holds_what_was_there_a_moment_before(tmp_path):
    """Not merely A copy: the copy as it stood immediately before the restore."""
    slot = _slot(tmp_path,
                 {"description": "edited after measuring", "run_number": 3},
                 {"description": "measurement-time text"})
    VS.restore_slot(slot)
    kept = _archived(slot.live_dir)
    assert kept == {"description": "edited after measuring", "run_number": 3}


def test_nothing_is_archived_when_the_snapshot_carries_no_side_file(tmp_path):
    """No needless copy: an archive is for a file actually being replaced."""
    live = tmp_path / "runs" / "run1"
    live.mkdir(parents=True)
    (live / "meta.json").write_text(json.dumps({"a": 1}), encoding="utf-8")
    snap = live / "chart"
    snap.mkdir()
    (snap / "chart.ti2").write_text("a chart", encoding="utf-8")
    slot = _RunLikeSlot(live, snap)
    VS.restore_slot(slot)
    assert _archived(live) is None
    assert json.loads((live / "meta.json").read_text(encoding="utf-8")) == {"a": 1}, \
        "a snapshot with no side file must leave the live one alone"
