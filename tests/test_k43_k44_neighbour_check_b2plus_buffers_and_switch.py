"""k43 and k44 (Knut #182 6059912998 "neighbour" answers, 6060201176).

k43: its own threshold per kind of chart; since beta 17 (Knut 6082015002)
the Neighbour limit of every chart type (10 / 5 / 3 / 10), and the approved
card line at the end of every card (6071004702, 6084176226).

k44: the Preferences checkbox Knut read as the neighbour check is the STRIP
TEST, so it is named so; the neighbour check has its own switch, which takes
effect LIVE: off removes the outlines it caused, on shows them again, and
what a re-read confirmed or corrected is kept across the toggles.
"""
from __future__ import annotations

import pytest

from tests.test_neighbour_check_in_the_measure_tab import (  # noqa: F401
    _card, _flags, _info, _read_all, _red, _strip, _tab, _text, qapp)
from workflow import misread_settings as MS
from workflow import measurement_messages as M
from workflow import neighbour_check as N
from workflow import patch_flags as pf


def test_the_defaults():
    from core.settings import DEFAULTS
    for k in MS.KINDS:
        assert DEFAULTS[MS.NEIGHBOUR_LIMIT_KEYS[k]] == \
            MS.NEIGHBOUR_LIMIT_DEFAULTS[k]
        assert DEFAULTS[MS.NEIGHBOUR_RADIUS_KEYS[k]] == \
            MS.NEIGHBOUR_RADIUS_DEFAULTS[k]
    assert DEFAULTS[N.SWITCH_KEY] is True
    s = {}
    assert [MS.neighbour_limit(s, k) for k in MS.KINDS] == [10, 5, 3, 10]
    assert [MS.neighbour_radius(s, k) for k in MS.KINDS] == [15, 30, 30, 30]
    assert N.enabled_from(s) is True


def test_a_pre_conditioning_chart_takes_its_own_limit(qapp, tmp_path):
    keys = {MS.NEIGHBOUR_LIMIT_KEYS["estimated"]: 50.0,
            MS.NEIGHBOUR_LIMIT_KEYS["accurate"]: 7.0}
    tab = _tab(tmp_path / "acc", accurate=True, settings=keys)
    _read_all(tab, {"D6": 0.55})
    assert tab._nb_check.limit == 7.0
    assert tab._nb_check.radius == 30.0
    assert _red(tab) == ["D6"]
    tab2 = _tab(tmp_path / "est", settings=keys)
    _read_all(tab2, {"D6": 0.55})
    assert tab2._nb_check.limit == 50.0
    assert tab2._nb_check.radius == 15.0
    assert _red(tab2) == []


def test_the_card_ends_with_the_approved_lines(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    lines = _card(_info(tab, "D6"))
    assert _text(lines).endswith(M._CARD_LATER_STRIP_S + " "
                                 + M._CARD_SEE_PREFS_S)
    # each its own topic, after an empty line (Knut 6071004702)
    from ui.tiff_preview import card_wrap
    later = card_wrap(M._CARD_LATER_STRIP_S)
    i = lines.index(later[0])
    assert lines[i - 1] == "" and lines[i + len(later)] == ""


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
    """Knut's names (6082015002), and help that says what the test does,
    in his four steps, with every value by chart type."""
    from ui.dialogs import settings_dialog as sd
    assert sd.STRIP_TEST_NAME == "Strip test"
    assert sd.NEIGHBOUR_CHECK_NAME == "Neighbour check"
    assert "not the neighbour check" in sd.STRIP_TEST_HELP
    h = sd.NEIGHBOUR_CHECK_HELP
    for part in ("**What it does:**", "**What it needs:**", "**When:**",
                 "**Patch colours and states:**", "Red", "Yellow", "Green",
                 "**Neighbour limit:**", "**Colour-neighbour radius:**",
                 "**Off:**", "2 to 4", "  4. when its own error minus that "
                 "median is more than the neighbour limit",
                 "10 / 15", "5 / 30", "3 / 30", "10 / 30",
                 "7 to 15"):
        assert part in h, part
    for t in (h, sd.STRIP_TEST_HELP, sd.SAME_READING_HELP,
              sd.STRIP_TEST_VERIFICATION_HELP, sd.LIMITS_PURPOSE_HELP):
        assert "—" not in t and "buffer" not in t.lower()


def test_the_preferences_save_the_switch_and_both_buffers(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    dlg = SettingsDialog(s, None)
    try:
        assert dlg._patch_neighbour_check.isChecked()
        assert dlg._neighbour_limit_spins["estimated"].value() == 10.0
        assert dlg._neighbour_limit_spins["accurate"].value() == 5.0
        dlg._patch_neighbour_check.setChecked(False)
        assert not dlg._neighbour_limit_spins["accurate"].isEnabled()
        assert not dlg._neighbour_radius_spins["calibration"].isEnabled()
        dlg._neighbour_limit_spins["accurate"].setValue(6.0)
        dlg._save_and_close()
        assert s.get(N.SWITCH_KEY) in (False, "false", 0)
        assert float(s.get(MS.NEIGHBOUR_LIMIT_KEYS["accurate"])) == 6.0
    finally:
        dlg.close()
