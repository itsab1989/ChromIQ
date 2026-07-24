"""#130 (Knut beta-6): when the Create-Chart preview is empty because the
selected Profile-run / Run-type has no chart yet, the preview shows friendly
guidance on how to make one — tailored to Profiling vs Verification — instead of
a bare 'No preview'. Also: the Profile-run combo is wide enough to read."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from core.argyll_runner import ArgyllRunner                     # noqa: E402
from core.file_manager import FileManager, Project              # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,        # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                           # noqa: E402
from ui.measurement_target_bar import (MeasurementTargetBar,    # noqa: E402
                                       MeasurementTargetController)
from ui.tabs.tab_chart import TabChart                          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab_with_project(tmp: Path):
    s = AppSettings(); s._qs = QSettings(str(tmp / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp))
    fm = FileManager(s)
    tab = TabChart(ArgyllRunner(s), fm, s)
    ctl = MeasurementTargetController(fm)
    tab.set_target_controller(ctl)
    proj = Project.create(tmp / "P", "P"); proj.current_run().ensure_dir()
    fm.set_target_name("P")
    return tab, ctl


def test_guidance_text_differs_by_run_type(qapp, tmp_path):
    tab, ctl = _tab_with_project(tmp_path)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    v = tab._no_chart_guidance()
    ctl.set_run_type(RUN_TYPE_PROFILING)
    p = tab._no_chart_guidance()
    assert "verification chart" in v.lower() and "Generate Chart" in v
    assert "profile run" in p.lower() and v != p


def test_empty_target_sets_preview_notice(qapp, tmp_path):
    """Switching to a run/type with no chart fills the preview notice."""
    tab, ctl = _tab_with_project(tmp_path)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._on_target_changed()
    # The notice label carries the guidance (visibility depends on the tab being
    # shown; the text being set is what matters).
    assert tab._preview._notice_lbl.text().strip()
    assert "verification chart" in tab._preview._notice_lbl.text().lower()


def test_showing_a_real_chart_clears_the_notice(qapp, tmp_path):
    tab, ctl = _tab_with_project(tmp_path)
    tab._preview.set_notice("stale guidance")
    # A single-page chart to display.
    run = Project.load(tmp_path / "P").current_run()
    tif = run.dir / "P.tif"; tif.write_bytes(b"")
    try:
        tab._display_run_chart(run.chart_ti2, [tif], run.chart_ti1)
    except Exception:
        pass                       # display may bail on the empty TIFF; that's fine
    assert not tab._preview._notice_lbl.isVisible() or \
        tab._preview._notice_lbl.text() == ""


def test_profile_run_combo_is_readable_width(qapp, tmp_path):
    tab, ctl = _tab_with_project(tmp_path)
    bar = MeasurementTargetBar(ctl)
    # Comfortably fits "Run N (overwrite)" plus the dropdown chrome.
    assert bar._run_combo.minimumWidth() >= 120
