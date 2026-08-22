"""The log's viewport font must follow the theme, not just the widget's.

`apply_theme` makes the log text heavier in light mode and normal in dark. It set
the weight on the QPlainTextEdit and on its QTextDocument — but not on the
VIEWPORT, which is what paints the placeholder. Going light → dark therefore left
the viewport at Weight.Black and the placeholder stayed visibly bolder: 3,331 ink
pixels against 4,441 in a rendered comparison.

It has never been reported because the next tab switch re-styles every widget and
repairs it by accident. That accidental repair is exactly what the pane-stylesheet
fix removes, so this had to be fixed first — the performance change would
otherwise have made a dormant bug visible and looked like the cause.

This test FAILS on master.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from PyQt6.QtCore import QSettings                  # noqa: E402
from PyQt6.QtWidgets import QApplication, QPlainTextEdit   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("first,second", [("light", "dark"), ("dark", "light")])
def test_the_log_viewport_weight_follows_a_theme_change(qapp, tmp_path, first, second):
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / f"{first}.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    win = MainWindow(s)
    try:
        for mode in (first, second):
            win.apply_theme(mode)
            logs = win.findChildren(QPlainTextEdit, "log")
            assert logs, "no log widgets to check"
            for log in logs:
                assert log.viewport().font().weight() == log.font().weight(), (
                    f"{mode}: the viewport paints at "
                    f"{log.viewport().font().weight()} while the widget is set to "
                    f"{log.font().weight()} — the placeholder will be the wrong "
                    "weight until something else happens to re-style it")
    finally:
        win.close()
