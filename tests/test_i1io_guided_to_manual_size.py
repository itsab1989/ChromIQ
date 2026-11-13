"""GUIDED -> MANUAL CARRIES THE PATCH SIZE GUIDED REALLY USED (review 5,
item 6; 4.3.33 too).

Guided's automatic size arrived in Manual as 0, which Manual showed as the
table's minimum (7 x 8.9 mm), so Manual generated 650 patches where Guided
built 528 (A4), or 1872 instead of 1518 (Letter, 3 pages). The i1iO's own
size (8 x 10 mm by default) now goes over."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


@pytest.fixture
def chart_tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("use_chromiq_layout_engine", True)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    yield tab
    tab.deleteLater()


@pytest.mark.parametrize("paper", ["A4", "Letter"])
def test_manual_shows_and_builds_guideds_size(chart_tab, paper):
    from PyQt6.QtWidgets import QApplication
    from workflow.i1io.table_facts import PATCH_ACROSS_MM, PATCH_ALONG_MM
    tab = chart_tab
    tab._switch_mode("guided")
    i = tab._instr_combo.findData("IO2")
    tab._instr_combo.setCurrentIndex(i)
    tab._instr_combo.activated.emit(i)
    tab._shared_set("guided", "paper", paper)
    QApplication.processEvents()
    guided = tab._creator._engine_total_patches(tab._collect_guided())
    tab._switch_mode("manual")
    QApplication.processEvents()
    r = tab._manual_layout_panel.get_recipe()
    assert (r.patch_w_mm, r.patch_h_mm) == (PATCH_ACROSS_MM.value,
                                            PATCH_ALONG_MM.value)
    manual = tab._creator._engine_total_patches(tab._collect_params())
    assert manual == guided
