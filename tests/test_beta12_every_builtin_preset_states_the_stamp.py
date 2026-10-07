"""Beta 12, #182 FINDINGS I: every built-in preset states "Stamp settings
down the right edge", and states it OFF.

Knut: all presets are designed and saved without the stamp. Until beta 11
only 41 of 189 built-ins said so; the other 148 (every ColorMunki "Fast/Slow
Reading Speed" chart, all 26 CR30 hexagon charts) left the checkbox where it
was, and on a new target that is the app's default, ON. Basti's A3 Plus 616
verification chart came out stamped that way (2026-10-07), and the CR30
hexagon charts' stamp ran over their patches.

The default for a NEW target was a question to Knut; he answered it in
#182 6045500910 ("stamp default OFF"): see
tests/test_beta12_a_new_target_opens_with_the_stamp_off.py.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from ui.tabs.tab_chart import KNUT_PRESETS, TabChart  # noqa: E402


def test_every_builtin_preset_states_the_stamp_off():
    assert len(KNUT_PRESETS) >= 189
    silent = [p.slug for p in KNUT_PRESETS if p.stamp_settings is None]
    assert silent == [], f"{len(silent)} built-ins leave the stamp alone"
    on = [p.slug for p in KNUT_PRESETS if p.stamp_settings is not False]
    assert on == []


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    return t


def _one_of_each_family():
    seen, out = set(), []
    for p in KNUT_PRESETS:
        fam = (p.group or p.instrument, p.layout_recipe is not None, p.engine)
        if fam not in seen:
            seen.add(fam)
            out.append(p)
    return out


@pytest.mark.parametrize("preset", _one_of_each_family(), ids=lambda p: p.slug)
def test_loading_a_preset_never_leaves_the_stamp_on(tab, preset):
    box = tab._manual_stamp_cmd_check
    box.setChecked(True)
    tab._seed_knut_preset(preset.key)
    assert box.isChecked() is False


def test_every_cr30_preset_switches_it_off(tab):
    cr30 = [p for p in KNUT_PRESETS if p.group == "CR30"]
    assert len(cr30) == 26
    box = tab._manual_stamp_cmd_check
    for p in cr30:
        box.setChecked(True)
        tab._seed_knut_preset(p.key)
        assert box.isChecked() is False, p.slug
