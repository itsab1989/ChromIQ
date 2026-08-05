"""#130 — where a run's description and chart notes are stored.

The Test Plan Specification's §1 and §2 (docs/design/per_run_description.md).
Knut's rule, which the whole design rests on: **one file per keystroke, never
two.** The Profile run picks the folder; the Run type picks the file.
"""
from __future__ import annotations

import json

import pytest

from core.file_manager import CalibrationMeta, RunMeta


# ---- T1.1 / T1.2: the fields exist and default empty ---------------------
def test_a_run_starts_with_no_description_and_no_notes():
    meta = RunMeta()
    assert meta.description == ""
    assert meta.chart_notes == ""


def test_a_calibration_starts_with_no_description_and_no_notes():
    meta = CalibrationMeta()
    assert meta.description == ""
    assert meta.chart_notes == ""


def test_a_meta_written_before_this_feature_still_loads():
    """T1.1 — absent is empty, which is the honest state of every older run."""
    older = {"run_id": "run1", "created_at": "2026-01-01", "status": "complete"}
    meta = RunMeta.from_dict(older)
    assert meta.run_id == "run1"
    assert meta.description == ""
    assert meta.chart_notes == ""


def test_a_meta_from_a_newer_build_does_not_crash_an_older_one():
    """Unknown keys are dropped, not raised on — the same rule RunMeta already
    used, applied to the new file so cal/meta.json cannot become a trap."""
    meta = CalibrationMeta.from_dict(
        {"description": "Baryta, new ink", "something_from_2027": 42})
    assert meta.description == "Baryta, new ink"


# ---- T2.5 / T2.6: the calibration writes its OWN file --------------------
def test_the_calibration_keeps_its_text_in_its_own_meta(tmp_path):
    from core.file_manager import Calibration

    cal = Calibration(tmp_path)
    cal.save_meta(CalibrationMeta(description="Canson Baryta, warm room",
                                  chart_notes="printed 2026-08-05"))
    assert cal.meta_path.exists()
    on_disk = json.loads(cal.meta_path.read_text(encoding="utf-8"))
    assert on_disk["description"] == "Canson Baryta, warm room"
    assert cal.load_meta().chart_notes == "printed 2026-08-05"


def test_a_calibration_with_no_meta_reads_as_empty(tmp_path):
    from core.file_manager import Calibration

    assert Calibration(tmp_path).load_meta() == CalibrationMeta()


def test_an_unreadable_calibration_meta_reads_as_empty_rather_than_raising(tmp_path):
    """A truncated file must not stop the tab from opening. Absent and broken
    are the same thing here: there is nothing to show."""
    from core.file_manager import Calibration

    cal = Calibration(tmp_path)
    cal.dir.mkdir(parents=True, exist_ok=True)
    cal.meta_path.write_text("{ this is not json", encoding="utf-8")
    assert cal.load_meta() == CalibrationMeta()


# ---- T8.5 / T8.6: nothing else moved ------------------------------------
def test_the_two_new_keys_did_not_bump_the_schema():
    """T8.6 — no migration runs for this. An absent key IS the value."""
    import inspect

    from core import file_manager

    src = inspect.getsource(file_manager)
    # The schema version constant is unchanged at 3; a test that asserts the
    # number would fail for unrelated reasons, so assert the RELATION: nothing
    # in the migration code mentions either new field.
    assert "def _migrate" in src, "the migration code moved; re-point this test"
    migrate = src[src.index("def _migrate"):]
    assert '"description"' not in migrate, (
        "the run description is being migrated; it should not be — an absent "
        "key already means empty, which is what every older run honestly is"
    )
    assert '"chart_notes"' not in migrate
