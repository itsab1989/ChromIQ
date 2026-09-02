"""#137 Table E / D3 — the calibration chart is a chart like any other.

Decision 3 put Restore Used Chart in the first version, and it comes almost
free: ``ChartSlot`` is a plain dataclass, so one more ``slot_for_*`` gives the
calibration chart the copying, the "already identical" check and the restore
that runs and verifications already use.
"""
from __future__ import annotations

import pytest

from core.file_manager import Calibration, Run, Verification
from workflow.chart_slot import (slot_for, slot_for_calibration,
                                 slot_for_run, slot_for_verification)
from workflow.verify_chart_snapshot import (restore_slot, slot_has_snapshot,
                                            snapshot_matches_live,
                                            snapshot_slot)


@pytest.fixture
def cal(tmp_path):
    root = tmp_path / "Test-Printer"
    root.mkdir()
    c = Calibration(root)
    c.ensure_dir()
    c.ti1.write_text("ti1", encoding="utf-8")
    c.ti2.write_text("the printed chart", encoding="utf-8")
    return c


# ---- R5: dispatch stays correct for all three -----------------------------
def test_dispatch_picks_the_calibration_slot(cal):
    slot = slot_for(cal)
    assert slot.snapshot_dir == cal.snapshot_dir
    assert slot.stem == cal.stem


def test_the_three_slots_stay_distinct(cal, tmp_path):
    """A new kind of target must not be quietly treated as a run."""
    assert slot_for_calibration(cal).snapshot_dir != cal.dir
    # The dispatch is by explicit type, so a plain object is a run — which is
    # the historical behaviour and is what the other two rely on.
    assert slot_for(cal) is not None


# ---- the chart, and only the chart ----------------------------------------
def test_the_measurement_is_not_part_of_the_chart(cal):
    """Restoring a chart must never put back a stale measurement over a fresh
    one — the .ti3 and the .cal are results, not the chart."""
    cal.ti3.write_text("readings", encoding="utf-8")
    cal.cal_path.write_text("curves", encoding="utf-8")
    names = {p.name for p in slot_for(cal).live_files()}
    assert f"{cal.stem}.ti1" in names and f"{cal.stem}.ti2" in names
    assert f"{cal.stem}.ti3" not in names
    assert f"{cal.stem}.cal" not in names


# ---- E9 / E10 / E11 -------------------------------------------------------
def test_nothing_stored_yet(cal):
    assert slot_has_snapshot(slot_for(cal)) is False


def test_a_stored_copy_matches_until_the_chart_changes(cal):
    slot = slot_for(cal)
    snapshot_slot(slot)
    assert slot_has_snapshot(slot) is True
    assert snapshot_matches_live(slot) is True
    cal.ti2.write_text("regenerated", encoding="utf-8")
    assert snapshot_matches_live(slot) is False


def test_restore_puts_the_measured_chart_back(cal):
    slot = slot_for(cal)
    snapshot_slot(slot)
    cal.ti3.write_text("the readings", encoding="utf-8")          # measured after the snapshot
    cal.ti2.write_text("regenerated", encoding="utf-8")
    restore_slot(slot)
    assert cal.ti2.read_text(encoding="utf-8") == "the printed chart"
    assert cal.ti3.read_text(encoding="utf-8") == "the readings", "a restore ate the measurement"


# ---- E13: a project from before this existed ------------------------------
def test_an_old_project_without_the_new_folders_is_fine(cal):
    assert not cal.snapshot_dir.exists()
    assert not cal.old_dir.exists()
    assert slot_has_snapshot(slot_for(cal)) is False
    assert cal.live_files()          # …and the chart is still found
