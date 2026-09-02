"""A calibration restore brings back the stored chart AND its notes.

Knut supplied his real `cal/` folder (#130) and asked for it to be driven on
screen: *"Restoring the chart does not restore the chart notes. both chart
sidecar json files have different notes in them."* His two sidecars differed
exactly as he said — the live one held a 120-patch chart noted "new calib note",
the stored one a 224-patch chart noted "calibration test".

Driven on screen against beta.167 it passes: the field ends on "calibration
test" and the live sidecar becomes the 224-patch chart. The fault was the one
fixed in beta.165, where the page rebuild redrew the selected *run's* chart over
the restored calibration.

This test holds the file half of that in place without needing a window, using
the same `ChartSlot` the button drives.
"""
import json
import shutil

import pytest

from core.file_manager import Project
from workflow.chart_slot import slot_for_calibration
from workflow.verify_chart_snapshot import restore_slot, snapshot_slot


def _sidecar(path, notes, patches):
    path.write_text(json.dumps({
        "ink_channels": ["r", "g", "b"],
        "chart_notes": notes,
        "run_description": "",
        "stamp_commands": False,
        "layout": {"patches": [{"loc": f"A{i}"} for i in range(patches)]},
    }), encoding="utf-8")


@pytest.fixture
def calibration(tmp_path):
    proj = Project.create(tmp_path, "Demo")
    cal = proj.calibration
    cal.ensure_dir()
    return cal


def test_the_stored_chart_and_its_notes_both_come_back(calibration):
    """Knut's exact sequence, in files."""
    cal, stem = calibration, calibration.stem
    # The chart he measured: 224 patches, noted "calibration test".
    (cal.dir / f"{stem}.ti1").write_text("TI1 original", encoding="utf-8")
    (cal.dir / f"{stem}.ti2").write_text("TI2 original", encoding="utf-8")
    _sidecar(cal.dir / f"{stem}.channels.json", "calibration test", 224)
    m = cal.load_meta(); m.chart_notes = "calibration test"; cal.save_meta(m)
    snapshot_slot(slot_for_calibration(cal))

    # …then he made a different chart: 120 patches, a different note.
    (cal.dir / f"{stem}.ti2").write_text("TI2 replacement", encoding="utf-8")
    _sidecar(cal.dir / f"{stem}.channels.json", "new calib note", 120)
    m = cal.load_meta(); m.chart_notes = "new calib note"; cal.save_meta(m)

    result = restore_slot(slot_for_calibration(cal))
    assert result.ok, result.error

    doc = json.loads((cal.dir / f"{stem}.channels.json").read_text(encoding="utf-8"))
    assert doc["chart_notes"] == "calibration test", (
        "the restored sidecar carries the replacement chart's notes"
    )
    assert len(doc["layout"]["patches"]) == 224, (
        "the restored chart is not the one that was measured"
    )
    assert (cal.dir / f"{stem}.ti2").read_text(encoding="utf-8") == "TI2 original"


def test_the_snapshot_carries_the_sidecar_at_all(calibration):
    """If the sidecar does not travel, no restore can bring the notes back."""
    cal, stem = calibration, calibration.stem
    (cal.dir / f"{stem}.ti1").write_text("TI1", encoding="utf-8")
    (cal.dir / f"{stem}.ti2").write_text("TI2", encoding="utf-8")
    _sidecar(cal.dir / f"{stem}.channels.json", "notes that must travel", 60)
    # meta.json is a *side* file: it travels only once it exists, which in the
    # app it always does by this point. Knut's real cal/chart/ has it.
    m = cal.load_meta(); m.chart_notes = "notes that must travel"; cal.save_meta(m)
    names = [p.name for p in slot_for_calibration(cal).files_to_copy()]
    assert f"{stem}.channels.json" in names
    assert "meta.json" in names, "the chart's own meta must travel with it"


def test_restoring_twice_is_harmless(calibration):
    """The button can be pressed again; it must not degrade what it restored."""
    cal, stem = calibration, calibration.stem
    (cal.dir / f"{stem}.ti1").write_text("TI1", encoding="utf-8")
    (cal.dir / f"{stem}.ti2").write_text("TI2 original", encoding="utf-8")
    _sidecar(cal.dir / f"{stem}.channels.json", "keep me", 90)
    snapshot_slot(slot_for_calibration(cal))
    (cal.dir / f"{stem}.ti2").write_text("TI2 replacement", encoding="utf-8")

    for _ in range(2):
        assert restore_slot(slot_for_calibration(cal)).ok
    doc = json.loads((cal.dir / f"{stem}.channels.json").read_text(encoding="utf-8"))
    assert doc["chart_notes"] == "keep me"
    assert (cal.dir / f"{stem}.ti2").read_text(encoding="utf-8") == "TI2 original"
