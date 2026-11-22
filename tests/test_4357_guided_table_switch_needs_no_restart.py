"""Preferences > Beta > "Guided, step by step measurement" takes effect
without a restart (4.3.57, item 11), and its help says so.

The table window reads the switch when START MEASUREMENT builds the job
(`ui.i1io_table_window._build_job`: `guided(self._settings)`), straight from
the settings store; Preferences writes it on OK. So the next START uses the
new value; a measurement already running keeps how it began.
"""
from PyQt6.QtCore import QSettings


def test_ok_in_preferences_reaches_the_next_start(qapp, tmp_path,
                                                  monkeypatch):
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    from ui.i1io_table_window import guided
    ini = str(tmp_path / "s.ini")
    s = AppSettings()
    s._qs = QSettings(ini, QSettings.Format.IniFormat)
    s.set("i1io_support_beta", True)
    assert guided(s) is True
    dlg = SettingsDialog(s, None)
    dlg._i1io_ask_check.setChecked(False)
    monkeypatch.setattr(dlg, "exec", lambda *a: 0, raising=False)
    dlg._save_and_close()
    # the same store, read the way the table window reads it at START
    assert guided(s) is False
    other = AppSettings()
    other._qs = QSettings(ini, QSettings.Format.IniFormat)
    assert guided(other) is False


def test_the_help_says_it_needs_no_restart():
    from workflow import measurement_messages as M
    body = M.M_I1IO_GUIDED_HELP.render(countdown="")[1]
    assert "without restarting ChromIQ" in body
    assert "next START MEASUREMENT" in body
