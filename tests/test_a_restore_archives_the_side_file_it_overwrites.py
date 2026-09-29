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


# ---------------------------------------------------------------------------
# Knut's ruling, 2026-09-22 (#182 comment 5775260868): only the CHART's fields
# ---------------------------------------------------------------------------
def test_restore_takes_only_the_charts_fields_from_the_snapshot(tmp_path):
    """*"Agreed. The Description and the seven compliance fields are the run's
    and stay."* and, of the rest: *"It sounds like they should survive too."*

    MUTATION: write the snapshot's meta.json over the live one again (the
    `shutil.copy2` for it) and every assert below on a live field goes red.
    """
    live = {"description": "what the user has now",
            "compliance_set_id": "chromiq_default",
            "compliance_set_label": "ChromIQ default (recommended)",
            "compliance_thresholds": {"all_de00_avg": 2.0},
            "compliance_bound_at": "2026-09-01T10:00:00",
            "compliance_unlocked": False,
            "compliance_columns": ["x"],
            "report_type": "t2_full_colour_check",
            "status": "complete",
            "profile_built_from": "run1/P.ti3",
            "create_chart_settings": {"targen_-f": 400},
            "editor_recipe": {"patches": 400}}
    snap = {"description": "what it was at measurement time",
            "status": "in_progress",
            "create_chart_settings": {"targen_-f": 210},
            "editor_recipe": {"patches": 210}}
    slot = _slot(tmp_path, live, snap)
    VS.restore_slot(slot)
    got = json.loads((slot.live_dir / "meta.json").read_text(encoding="utf-8"))
    # the chart's fields come from the snapshot...
    assert got["create_chart_settings"] == {"targen_-f": 210}
    assert got["editor_recipe"] == {"patches": 210}
    # ...the run's stay live
    assert got["description"] == "what the user has now"
    for k in ("compliance_set_id", "compliance_set_label",
              "compliance_thresholds", "compliance_bound_at",
              "compliance_unlocked", "compliance_columns", "report_type"):
        assert got[k] == live[k], k
    # ...and so does the run's own record
    assert got["status"] == "complete"
    assert got["profile_built_from"] == "run1/P.ti3"
    # the whole previous file is still archived, as before
    assert _archived(slot.live_dir)["create_chart_settings"] == {"targen_-f": 400}


def test_a_snapshot_meta_that_cannot_be_read_changes_no_live_field(tmp_path):
    """A broken snapshot restores no field, and the restore still completes
    (the rollback handles OSError only, so a ValueError must not escape)."""
    live = {"description": "keep", "create_chart_settings": {"targen_-f": 400}}
    slot = _slot(tmp_path, live, {})
    (slot.snapshot_dir / "meta.json").write_text("{not json", encoding="utf-8")
    VS.restore_slot(slot)
    got = json.loads((slot.live_dir / "meta.json").read_text(encoding="utf-8"))
    assert got == live
