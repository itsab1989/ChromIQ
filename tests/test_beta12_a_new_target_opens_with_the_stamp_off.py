"""Beta 12: "Stamp settings down the right edge" is OFF on a new target
(Knut, #182 6045500910, answer 3: "Yes, stamp default OFF, and all stored
built-in presets shall default have stamp OFF"; per_target_settings.md §4d).

A target with nothing stored opens on the saved defaults, else on factory
(§4, S4/S5): the factory setting is now OFF. A target whose record holds the
stamp keeps it, and a user who saved defaults with the stamp ON gets it ON.
Until beta 11 the factory setting was ON, which is how Basti's fresh
verification target of 2026-10-07 came out stamped (FINDINGS I).
"""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from ui.tabs import tab_chart  # noqa: E402
from ui.tabs.tab_chart import TabChart  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _tab(tmp_path, **settings):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    for k, v in settings.items():
        s.set(k, v)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    return t


def test_the_factory_setting_is_off():
    assert tab_chart.STAMP_FACTORY_DEFAULT is False


def test_a_new_target_with_nothing_stored_opens_with_the_stamp_off(qapp,
                                                                   tmp_path):
    t = _tab(tmp_path)
    t._manual_stamp_cmd_check.setChecked(True)     # the run just left had it
    t._apply_ui_state({})
    assert t._manual_stamp_cmd_check.isChecked() is False


def test_a_fresh_window_starts_with_the_stamp_off(qapp, tmp_path):
    assert _tab(tmp_path)._manual_stamp_cmd_check.isChecked() is False


def test_a_target_that_stored_the_stamp_keeps_it(qapp, tmp_path):
    t = _tab(tmp_path)
    t._apply_ui_state({"stamp": True})
    assert t._manual_stamp_cmd_check.isChecked() is True
    t._apply_ui_state({"stamp": False})
    assert t._manual_stamp_cmd_check.isChecked() is False


def test_saved_defaults_with_the_stamp_on_still_win(qapp, tmp_path):
    """§4: "factory settings, or the saved defaults if the user has any"."""
    t = _tab(tmp_path, chart_stamp_commands=True)
    t._apply_ui_state({})
    assert t._manual_stamp_cmd_check.isChecked() is True
