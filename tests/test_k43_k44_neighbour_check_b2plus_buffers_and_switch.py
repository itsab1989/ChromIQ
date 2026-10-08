"""k43 and k44 (Knut #182 6059912998 "neighbour" answers, 6060201176).

k43: B2+ in the Measure tab; one buffer for a chart made with a
pre-conditioning profile (default 5) and one for other charts (default 10);
the approved card line "Checked again after each strip: a patch can turn red
later, when patches near it in colour are read".

k44: the Preferences checkbox Knut read as the neighbour check is the STRIP
TEST, so it is named so; the neighbour check has its own switch, which takes
effect LIVE: off removes the outlines it caused, on shows them again, and
what a re-read confirmed or corrected is kept across the toggles.
"""
from __future__ import annotations

import pytest

from tests.test_neighbour_check_in_the_measure_tab import (  # noqa: F401
    _card, _flags, _info, _read_all, _red, _strip, _tab, qapp)
from workflow import measurement_messages as M
from workflow import neighbour_check as N
from workflow import patch_flags as pf


def test_the_defaults():
    from core.settings import DEFAULTS
    assert DEFAULTS[N.BUFFER_KEY] == 10.0
    assert DEFAULTS[N.BUFFER_ACCURATE_KEY] == 5.0
    assert DEFAULTS[N.SWITCH_KEY] is True
    s = {}
    assert N.buffer_from(s) == 10.0 and N.buffer_from(s, accurate=True) == 5.0
    assert N.enabled_from(s) is True


def test_a_pre_conditioning_chart_takes_its_own_buffer(qapp, tmp_path):
    tab = _tab(tmp_path / "acc", accurate=True,
               settings={N.BUFFER_KEY: 50.0, N.BUFFER_ACCURATE_KEY: 7.0})
    _read_all(tab, {"D6": 0.55})
    assert tab._nb_check.buffer == 7.0
    assert _red(tab) == ["D6"]
    tab2 = _tab(tmp_path / "est", settings={N.BUFFER_KEY: 50.0,
                                            N.BUFFER_ACCURATE_KEY: 7.0})
    _read_all(tab2, {"D6": 0.55})
    assert tab2._nb_check.buffer == 50.0
    assert _red(tab2) == []


def test_the_card_carries_the_approved_line(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    lines = _card(_info(tab, "D6"))
    assert M._CARD_NB_LATER_1 in lines and M._CARD_NB_LATER_2 in lines
    assert (M._CARD_NB_LATER_1 + " " + M._CARD_NB_LATER_2).rstrip(".") \
        == M.NB_CHECKED_AGAIN


def test_switched_off_live_the_outline_goes_and_comes_back(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    assert _red(tab) == ["D6"]
    tab._session_live = True                 # during a measurement, too
    tab._settings.set(N.SWITCH_KEY, False)
    tab.refresh_patch_flags()                # what Preferences' OK calls
    assert _red(tab) == []
    assert _info(tab, "D6")["neighbour"] is None
    assert tab.neighbour_summary_facts() is None
    tab._settings.set(N.SWITCH_KEY, True)
    tab.refresh_patch_flags()
    assert _red(tab) == ["D6"]
    assert _info(tab, "D6")["neighbour"]["n"] >= 2


def test_read_while_off_it_shows_once_switched_on(qapp, tmp_path):
    tab = _tab(tmp_path, settings={N.SWITCH_KEY: False})
    _read_all(tab, {"D6": 0.55})
    assert _red(tab) == []
    tab._settings.set(N.SWITCH_KEY, True)
    tab._nb_applied_on = False
    tab.refresh_neighbour_switch()
    assert _red(tab) == ["D6"]


def test_yellow_and_green_are_remembered_across_the_toggles(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55, "B4": 0.55})
    assert set(_red(tab)) == {"D6", "B4"}
    tab._on_strip_measured(_strip("D", {"D6": 0.55}))     # same: yellow
    tab._on_strip_measured(_strip("B"))                   # fits: green
    assert _flags(tab)["D6"] == pf.FLAG_CONFIRMED
    assert _flags(tab)["B4"] == pf.FLAG_CORRECTED
    tab._session_live = True
    for on in (False, True):
        tab._settings.set(N.SWITCH_KEY, on)
        tab.refresh_patch_flags()
    assert _flags(tab)["D6"] == pf.FLAG_CONFIRMED
    assert _flags(tab)["B4"] == pf.FLAG_CORRECTED


def test_the_preferences_name_both_functions(qapp):
    """k44: each checkbox starts with the name of the function it switches,
    and the help cards carry those names; the neighbour check's help says
    what Knut asked for and carries his approved line whole."""
    from ui.dialogs import settings_dialog as sd
    assert sd.STRIP_TEST_LABEL.startswith("Strip test: ")
    assert sd.NEIGHBOUR_CHECK_LABEL.startswith("Neighbour check: ")
    assert "not the neighbour check" in sd.STRIP_TEST_HELP
    h = sd.NEIGHBOUR_CHECK_HELP
    assert M.NB_CHECKED_AGAIN in h
    for part in ("**What it does:**", "**What it needs:**", "**Limits:**",
                 "**Patch colours and states:**", "Red", "Yellow", "Green",
                 "**The two buffers:**", "**Off:**", "2 to 4", "ΔE 15"):
        assert part in h, part
    assert "—" not in h and "—" not in sd.STRIP_TEST_HELP


def test_the_preferences_save_the_switch_and_both_buffers(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    dlg = SettingsDialog(s, None)
    try:
        assert dlg._patch_neighbour_check.isChecked()
        assert dlg._patch_neighbour_spin.value() == 10.0
        assert dlg._patch_neighbour_acc_spin.value() == 5.0
        dlg._patch_neighbour_check.setChecked(False)
        assert not dlg._patch_neighbour_acc_spin.isEnabled()
        dlg._patch_neighbour_acc_spin.setValue(6.0)
        dlg._save_and_close()
        assert s.get(N.SWITCH_KEY) in (False, "false", 0)
        assert float(s.get(N.BUFFER_ACCURATE_KEY)) == 6.0
        assert dlg._patch_fence_check.text() == sd_label()
    finally:
        dlg.close()


def sd_label():
    from core.i18n import tr
    from ui.dialogs.settings_dialog import STRIP_TEST_LABEL
    return tr(STRIP_TEST_LABEL)
