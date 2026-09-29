"""The "Print info in left clip area" tick box sits directly under "Stamp
settings down the right edge" (Basti, 2026-09-29, on Knut's screenshot of
4.3.2: "checkbox should be under the one above it"; B8-1705).

Its row's indent was held at the label column's full width while the stamp
row's indent above only has a maximum and sits narrower, so the second box
started 160 px further right (x=202 against x=41, offscreen)."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from PyQt6.QtCore import QPoint, QSettings                     # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402


@pytest.fixture
def tab(tmp_path):
    QApplication.instance() or QApplication([])
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    t.resize(900, 1400)
    t.show()
    yield t
    t.close()
    t.deleteLater()


@pytest.mark.parametrize("width", [900, 700])
def test_the_left_clip_box_starts_where_the_stamp_box_starts(tab, width):
    app = QApplication.instance()
    tab._manual_engine_check.setChecked(False)
    tab._manual_instr_pw.set_value("i1")
    tab._manual_paper_pw.set_value("A3")
    tab._manual_lb_pw.set_value(False)
    tab._update_manual_lb_visibility()
    tab.resize(width, 1400)
    for _ in range(5):
        app.processEvents()
    assert tab._manual_left_clip_row.isVisible()
    a = tab._manual_stamp_cmd_check.mapTo(tab, QPoint(0, 0)).x()
    b = tab._manual_left_clip_check.mapTo(tab, QPoint(0, 0)).x()
    assert a == b, f"stamp box at x={a}, left-clip box at x={b}"
