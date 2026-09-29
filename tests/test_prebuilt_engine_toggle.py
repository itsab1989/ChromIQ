"""Enabling the ChromIQ layout engine on a *prebuilt-files* built-in preset
must reveal the engine layout panel (Knut).

Before the fix, ``_refresh_manual_command_preview`` returned early for a
prebuilt-active preset (e.g. "TC9.18 extended greys by Pharmacist"), skipping
the block that swaps the printtarg layout group for the engine panel. So the
engine toggle appeared to do nothing — only the old printtarg layout stayed
visible, and the user could not build their own chart on the new layout.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from tests._prebuilt_fixture import PHOTOCARD600_KEY as PHOTOCARD600_PRESET_KEY  # noqa: E402
from ui.tabs.tab_chart import TabChart  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _make_tab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", False)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._switch_mode("manual")
    if not tab._manual_panel_inited:
        tab._init_manual_layout_panel()
    return tab, s


def test_prebuilt_preset_reveals_engine_panel_on_toggle(prebuilt_bundles, qapp, tmp_path):
    tab, s = _make_tab(qapp, tmp_path)
    tab.show()
    qapp.processEvents()

    # Simulate a prebuilt-files preset (i1Pro) having been loaded: printtarg
    # layout shown, engine off.
    tab._set_manual_value("printtarg", "-i", "i1")
    tab._prebuilt_active = True
    tab._prebuilt_key = PHOTOCARD600_PRESET_KEY
    tab._refresh_manual_command_preview()
    qapp.processEvents()
    assert tab._manual_layout_grp.isHidden()          # engine panel hidden
    assert not tab._manual_printtarg_grp.isHidden()   # printtarg shown

    # User enables "Use the ChromIQ layout engine" → engine panel must appear
    # and the printtarg layout must give way to it.
    tab._manual_engine_check.setChecked(True)
    qapp.processEvents()
    assert not tab._manual_layout_grp.isHidden(), \
        "engine panel stayed hidden on a prebuilt preset (Knut's bug)"
    assert tab._manual_printtarg_grp.isHidden()

    # Reversible: turning it back off restores the printtarg layout.
    tab._manual_engine_check.setChecked(False)
    qapp.processEvents()
    assert tab._manual_layout_grp.isHidden()
    assert not tab._manual_printtarg_grp.isHidden()
