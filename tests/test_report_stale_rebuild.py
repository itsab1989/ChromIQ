"""A saved measurement report from an older ChromIQ (older REPORT_SCHEMA, whose
de00 predates the avg_all/max_all metric set) must be rebuilt from its run's own
.ti3 so the window still shows the colour-accuracy figures and the trend has
usable points (Knut: a project full of valid .ti2/.ti3 showed "no design
reference" and an empty trend because the cached reports were stale)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.dialogs.measurement_report_dialog import MeasurementReportDialog  # noqa: E402

_TI2 = """CTI1

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 3
BEGIN_DATA
1 "A1" 100 100 100 95.0 100.0 108.0
2 "A2" 0 0 0 1.0 1.0 1.0
3 "A3" 100 0 0 41.0 21.0 2.0
END_DATA
"""
_TI3 = _TI2.replace("CTI1", "CTI3").replace("41.0 21.0 2.0", "36.0 18.0 3.0")

# An old-schema saved report: de00 carries only the legacy metric keys.
_OLD_REPORT = {
    "schema": 2,
    "created": "2026-01-02T10:00:00",
    "chart": "c",
    "patches": 3,
    "de00": {"n": 3, "mean": 4.2, "median": 4.0, "min": 0.1, "max": 8.0},
}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _make_run(tmp_path: Path) -> Path:
    run = tmp_path / "runs" / "run1"
    run.mkdir(parents=True)
    (run / "c.ti2").write_text(_TI2, encoding="utf-8")
    (run / "c.ti3").write_text(_TI3, encoding="utf-8")
    reps = run / "reports"
    reps.mkdir()
    (reps / "report_2026-01-02_10-00-00.json").write_text(json.dumps(_OLD_REPORT), encoding="utf-8")
    return run


def test_stale_report_is_rebuilt_from_ti3(qapp, tmp_path, settings=None):
    from core.settings import AppSettings
    dlg = MeasurementReportDialog(AppSettings(), initial_ti3=None)
    run = _make_run(tmp_path)
    name, runs = dlg._gather_runs(run / "c.ti3")
    assert len(runs) == 1
    rep = runs[0]
    # Rebuilt to the current schema/metrics (design reference used, avg_all set)…
    assert rep.get("reference_source") == "design"
    assert (rep.get("de00") or {}).get("avg_all") is not None
    # …while the ORIGINAL saved date is preserved so the trend timeline is intact.
    assert rep.get("created") == "2026-01-02T10:00:00"


def test_current_schema_report_is_left_as_is(qapp, tmp_path):
    """A report already at the current schema is used verbatim (no rebuild)."""
    from core.settings import AppSettings
    from workflow.measurement_report import build_report, REPORT_SCHEMA
    dlg = MeasurementReportDialog(AppSettings(), initial_ti3=None)
    run = tmp_path / "runs" / "run1"
    run.mkdir(parents=True)
    (run / "c.ti2").write_text(_TI2, encoding="utf-8")
    (run / "c.ti3").write_text(_TI3, encoding="utf-8")
    fresh = build_report(run / "c.ti3")
    fresh["created"] = "2025-12-31T09:00:00"
    fresh["_marker"] = "kept"
    reps = run / "reports"
    reps.mkdir()
    (reps / "report_2025-12-31_09-00-00.json").write_text(json.dumps(fresh), encoding="utf-8")
    assert fresh["schema"] == REPORT_SCHEMA
    _, runs = dlg._gather_runs(run / "c.ti3")
    assert runs[0].get("_marker") == "kept"      # not rebuilt
