"""The Verify tools' log line names where the report really went (P-INS-2).

Outside a ChromIQ project a Verify report lies straight beside the measurement
(Knut, #182 5944210498: nothing of ours, no reports/ folder, is made beside a
user's own files), but the log still said "(in the reports folder next to your
measurement)". In a project the old line stays right.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.dialogs.tools_dialogs import _report_saved_line  # noqa: E402


def test_outside_a_project_the_line_says_beside_the_measurement(tmp_path):
    m = tmp_path / "Downloads" / "m.ti3"
    m.parent.mkdir()
    m.write_text("x", encoding="utf-8")
    rp = m.parent / "Verify_Reference_1_m.txt"
    line = _report_saved_line(rp, m)
    assert "reports folder" not in line
    assert line.endswith("Verify_Reference_1_m.txt")
    assert "beside your measurement" in line


def test_in_a_project_the_line_names_the_reports_folder(tmp_path):
    from core.file_manager import Project
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    m = run.dir / "P.ti3"
    m.write_text("x", encoding="utf-8")
    rp = run.dir / "reports" / "Verify_Profile_1_P.txt"
    line = _report_saved_line(rp, m)
    assert "reports folder" in line
    assert "reports/Verify_Profile_1_P.txt" in line


def test_both_verify_tools_use_it():
    src = (Path(__file__).resolve().parent.parent / "ui" / "dialogs"
           / "tools_dialogs.py").read_text(encoding="utf-8")
    assert src.count("_report_saved_line(rp, self._measured)") == 2
