"""4.3.57, item 37: after opening another project, "Measured from Preview"
kept showing the PREVIOUS project's report.

Seen on screen (part A, and again for this fix): Report-A with a chart, then
Report-B (no chart yet) opened. The preview said "NO PREVIEW", while the frame
under it still held Report-A's TIFF and showed its margins, patch size and a
printer-edge warning, and the layout information's "on screen" column showed
Report-A's 525 patches. `_on_target_changed` cleared the preview for a target
with no chart and never told the frame.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from core.argyll_runner import ArgyllRunner                     # noqa: E402
from core.file_manager import FileManager, Project              # noqa: E402
from core.settings import AppSettings                           # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from ui.tabs.tab_chart import TabChart                          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(tmp: Path):
    s = AppSettings()
    s._qs = QSettings(str(tmp / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp))
    s.set("margin_inspector_show", True)
    fm = FileManager(s)
    tab = TabChart(ArgyllRunner(s), fm, s)
    ctl = MeasurementTargetController(fm)
    tab.set_target_controller(ctl)
    for name in ("A", "B"):
        Project.create(tmp / name, name).current_run().ensure_dir()
    return tab, fm


def test_opening_a_project_without_a_chart_empties_the_frame(qapp, tmp_path):
    """MUTATION: drop the `_set_margin_chart([], None)` from the no-chart
    branch of `_on_target_changed` and the frame keeps A's TIFF."""
    tab, fm = _tab(tmp_path)
    fm.set_target_name("A")
    tab._on_target_changed()
    # project A's chart is in the frame (what a Generate leaves there)
    a_tif = tmp_path / "A" / "runs" / "run1" / "A.tif"
    a_tif.write_bytes(b"")
    tab._margin_tiffs = [a_tif]
    tab._margin_report = object()
    fm.set_target_name("B")
    tab._on_target_changed()
    assert tab._margin_tiffs == []
    assert tab._margin_report is None
    assert not tab._margin_panel._placeholder.isHidden()
    assert tab._margin_panel._table.isHidden()
    assert tab._margin_panel.status_message() == ""
    tab.deleteLater()


def test_a_target_without_a_chart_and_an_empty_frame_is_left_alone(qapp,
                                                                  tmp_path):
    tab, fm = _tab(tmp_path)
    calls = []
    tab._set_margin_chart = lambda *a: calls.append(a)
    fm.set_target_name("B")
    tab._on_target_changed()
    assert calls == []          # nothing to forget, no needless re-measure
    tab.deleteLater()
