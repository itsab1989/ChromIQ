"""End-to-end: the Measurement Report dialog presents a verification report
correctly (#130) — verification title, Scope wording, and save location."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.file_manager import Project  # noqa: E402
from workflow.ti3_analysis import mark_verification_ti3  # noqa: E402

_TI2 = """CTI1

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 3
BEGIN_DATA
1 "A1" 100 100 100 96.42 100.0 82.53
2 "A2" 0 0 0 0.96 1.0 0.83
3 "A3" 100 0 0 41.0 21.0 2.0
END_DATA
"""
_TI3 = _TI2.replace("CTI1", "CTI3").replace("36.0 18.0 3.0", "35.0 18.0 3.0")


class _Settings:
    def __init__(self):
        self._d = {
            "appearance": "light",
            "report_title_profiling": "Measurement Report - Profiling of Printer",
            "report_title_verification": "Measurement Report - Verification of Profile",
            "report_add_profile_name": True,
            "report_pass_threshold_avg": 2.0,
            "report_pass_threshold_max": 3.0,
        }

    def get(self, k, d=None):
        return self._d.get(k, d)

    def set(self, k, v):
        self._d[k] = v


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def _verification_project(tmp_path: Path) -> Path:
    proj = Project.create(tmp_path / "Canon-Pro300", "Canon-Pro300")
    run = proj.current_run(); run.ensure_dir()
    # Reference chart at the run root (a self-verification) so the report finds
    # its design reference one/two levels up from the dated folder.
    (run.dir / "Canon-Pro300.ti2").write_text(_TI2)
    v = run.new_verification(); v.ensure_dir()
    vti3 = v.measurement_ti3
    vti3.write_text(_TI3)
    mark_verification_ti3(vti3)
    return vti3


def test_dialog_presents_verification_report(tmp_path):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    vti3 = _verification_project(tmp_path)

    dlg = MeasurementReportDialog(_Settings(), initial_ti3=vti3)
    runs = dlg._runs_for_report()
    assert runs, "the verification measurement should load as a report source"

    # It is recognised as a verification, so the title uses the verification
    # prefix (no date) and the Scope counts "verification run(s)".
    assert dlg._report_kind(runs) == "verification"
    title = dlg._report_title(runs)
    assert title.startswith("Measurement Report - Verification of Profile")
    assert "Canon-Pro300" in title              # profile name inserted
    # The date/time is NOT in the title (it's in the file name only, Knut).
    fname = dlg._report_filename(runs)
    assert fname.endswith(".pdf") and fname[:-4] != title  # filename adds the date

    scope = dlg._scope_html(runs)
    assert "verification run" in scope           # singular for one run
    assert "Date range:" in scope

    dlg.deleteLater()


def test_dialog_profiling_report_stays_profiling(tmp_path):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    (run.dir / "P.ti2").write_text(_TI2)
    ti3 = run.measurement_ti3
    ti3.write_text(_TI3)                          # NO verification marker

    dlg = MeasurementReportDialog(_Settings(), initial_ti3=ti3)
    runs = dlg._runs_for_report()
    assert dlg._report_kind(runs) == "profiling"
    assert dlg._report_title(runs).startswith("Measurement Report - Profiling of Printer")
    assert "verification run" not in dlg._scope_html(runs)
    dlg.deleteLater()
