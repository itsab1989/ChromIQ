"""k42 (Knut #182 6059912998, answer 3, confirmed by Sebastian): Guided has
no "Stamp settings down the right edge" control, so a Guided chart is printed
WITHOUT the stamp. Until beta 14 every Guided chart was stamped, because
`ChartParams.stamp_commands` defaults on and Guided never set it.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings

from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager
from core.settings import AppSettings


@pytest.fixture()
def tab(qapp, tmp_path):
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    # even someone whose saved defaults stamp, with Manual's box ticked
    s.set("chart_stamp_commands", True)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._manual_stamp_cmd_check.setChecked(True)
    yield t
    t.deleteLater()


def test_a_guided_chart_is_not_stamped(tab):
    p = tab._collect_guided()
    assert p.stamp_commands is False
    # and the layout keeps no strip clear for a stamp it will not print
    kw = tab._creator._engine_build_kwargs(p)
    assert kw["side_stamp"] is False


def test_manual_still_follows_its_checkbox(tab):
    assert tab._collect_manual().stamp_commands is True
    tab._manual_stamp_cmd_check.setChecked(False)
    assert tab._collect_manual().stamp_commands is False


def test_save_defaults_in_guided_keeps_manuals_stamp():
    """Review of beta 15: Guided's stamp is always off, so a Save as
    Defaults made in Guided must not write that into Manual's setting."""
    import inspect
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._on_save_defaults)
    i = src.index('s.set("chart_stamp_commands"')
    assert 'if self._current_mode() != "guided":' in src[max(0, i - 400):i]
