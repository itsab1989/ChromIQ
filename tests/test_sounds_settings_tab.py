"""#131 Phase 1: the Preferences → Sounds tab populates from settings and saves
the per-event choices + the user sounds folder."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QDialog  # noqa: E402

import core.sound as snd                            # noqa: E402
from core.settings import AppSettings               # noqa: E402
from ui.dialogs.settings_dialog import SettingsDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_sounds_tab_present_and_populated(qapp):
    dlg = SettingsDialog(AppSettings())
    tabs = [dlg._tabs.tabText(i) for i in range(dlg._tabs.count())]
    assert "Sounds" in tabs
    assert set(dlg._sound_combos) == set(snd.ALL_EVENTS)
    # Each combo starts on OFF and lists its event's choices.
    combo = dlg._sound_combos[snd.PATCH_OK]
    assert combo.itemData(0) == snd.OFF
    assert combo.currentData() == "tick"             # the default
    dlg.deleteLater()


def test_sounds_tab_saves_choices_and_folder(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(QDialog, "accept", lambda self: None)
    s = AppSettings()
    dlg = SettingsDialog(s)
    # Silence patch-ok, change the completion sound, set a user folder.
    dlg._sound_combos[snd.PATCH_OK].setCurrentIndex(0)          # OFF
    prof = dlg._sound_combos[snd.PROFILE_BUILT]
    prof.setCurrentIndex(prof.findData("fanfare"))
    dlg._sound_dir_edit.setText(str(tmp_path))

    dlg._save_and_close()

    assert s.get("sound_choice_patch_ok") == snd.OFF
    assert s.get("sound_choice_profile_built") == "fanfare"
    assert s.get("sound_folder") == str(tmp_path)
    dlg.deleteLater()
