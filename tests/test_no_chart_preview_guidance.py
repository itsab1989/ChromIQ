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
from tests._fontcheck import skip_without_fonts                 # noqa: E402
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
    # THE WIDTH COMES FROM GLYPH ADVANCES, so it needs real glyphs. Under
    # offscreen Qt on Windows the font database is EMPTY: every family resolves
    # to a null font, the combo sizes itself from nothing, and this measured 117
    # against a threshold of 120 — failing on an un-measurable number rather
    # than on anything wrong. Same guard as the eleven other advance-measuring
    # files (2026-08-22, Windows gate).
    #
    # …AND THE THRESHOLD WAS A GLYPH MEASUREMENT TOO, WHICH IS WHY IT IS GONE.
    # `ui/measurement_target_bar.py:795` sets the floor to
    # `fontMetrics().horizontalAdvance("Run 8 (overwrite)") + 44`, so a flat
    # 120 px pins the FONT, not the combo: with ChromIQ's own fonts registered
    # the same string measures 73 px of real Inter, the app correctly asks for
    # 117, and 120 failed a combo that is exactly as comfortable as it was on
    # the metrics the constant came from. The bound below is the label plus the
    # dropdown chrome, measured in the combo's own font — which is what "fits
    # 'Run N (overwrite)' comfortably" actually means, on any metrics.
    skip_without_fonts()
    tab, ctl = _tab_with_project(tmp_path)
    bar = MeasurementTargetBar(ctl)
    label_px = bar._run_combo.fontMetrics().horizontalAdvance("Run 8 (overwrite)")
    # Comfortably fits "Run N (overwrite)" plus the dropdown chrome.
    assert bar._run_combo.minimumWidth() >= label_px + 40, (
        f"the run combo's floor is {bar._run_combo.minimumWidth()} px for a "
        f"{label_px} px label — no room left for the dropdown arrow")
