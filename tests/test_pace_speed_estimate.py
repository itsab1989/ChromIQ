"""#131 (Knut, 2026-07-27): the live "min. strip reading speed" in Preferences.

His request, in his words: *"Add calculation for each instrument that updates
live based on the values set in 'Readings per second' and 'Minimum readings per
patch' … The calculated xx.y value above calculates live from the instruments
settings and the patches per strip value. User can change the patches per strip
value to see what the minimum speed will become for his instrument … This way
user can customise strip reading speed easily without having to do
calculations."*

So the figure has to be right, has to follow every one of the three inputs the
moment it changes, and has to say something sensible for an instrument whose
warning is switched off.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                   # noqa: E402
from PyQt6.QtWidgets import QApplication             # noqa: E402

from core.settings import AppSettings                # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dlg(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    from ui.dialogs.settings_dialog import SettingsDialog
    return SettingsDialog(s)


def test_the_default_strip_length_is_twenty(dlg):
    assert dlg._pace_patches_spin.value() == 20


def test_every_instrument_shows_a_figure(dlg):
    from core.measure_pace import MODEL_DEFAULTS
    assert set(dlg._pace_estimate) == set(MODEL_DEFAULTS)
    for lbl in dlg._pace_estimate.values():
        assert lbl.text().strip()


def test_the_arithmetic_is_the_one_used_while_measuring(dlg):
    """patches × minimum readings ÷ readings per second."""
    dlg._pace_patches_spin.setValue(15)
    dlg._pace_hz["colormunki"].setValue(50)
    dlg._pace_min["colormunki"].setValue(23)

    # 15 × 23 = 345 readings; 345 ÷ 50 = 6.9 s — Knut's own worked example.
    assert "6.9" in dlg._pace_estimate["colormunki"].text()
    assert "15 patches/strip" in dlg._pace_estimate["colormunki"].text()


def test_it_follows_the_readings_per_second(dlg):
    dlg._pace_patches_spin.setValue(20)
    dlg._pace_min["i1pro"].setValue(20)
    dlg._pace_hz["i1pro"].setValue(100)
    assert "4.0" in dlg._pace_estimate["i1pro"].text()

    dlg._pace_hz["i1pro"].setValue(200)
    assert "2.0" in dlg._pace_estimate["i1pro"].text()


def test_it_follows_the_minimum_readings(dlg):
    dlg._pace_patches_spin.setValue(10)
    dlg._pace_hz["i1pro2"].setValue(200)
    dlg._pace_min["i1pro2"].setValue(20)
    assert "1.0" in dlg._pace_estimate["i1pro2"].text()

    dlg._pace_min["i1pro2"].setValue(40)
    assert "2.0" in dlg._pace_estimate["i1pro2"].text()


def test_it_follows_the_strip_length(dlg):
    dlg._pace_hz["colormunki"].setValue(50)
    dlg._pace_min["colormunki"].setValue(23)
    dlg._pace_patches_spin.setValue(11)
    first = dlg._pace_estimate["colormunki"].text()
    dlg._pace_patches_spin.setValue(22)
    second = dlg._pace_estimate["colormunki"].text()
    assert first != second
    assert "5.1" in first and "10.1" in second      # 11 and 22 × 23 ÷ 50


def test_an_instrument_with_no_warning_says_so(dlg):
    """The SpectroScan is motorised: there is no swipe to be too quick, and a
    figure of 0.0 seconds would be nonsense."""
    dlg._pace_min["spectroscan"].setValue(0)         # "Off"
    assert dlg._pace_estimate["spectroscan"].text() == "no limit"


def test_the_strip_length_is_singular_for_one_patch(dlg):
    """Never "@ 1 patches/strip"."""
    dlg._pace_patches_spin.setMinimum(1)
    dlg._pace_patches_spin.setValue(1)
    dlg._pace_hz["i1pro"].setValue(100)
    dlg._pace_min["i1pro"].setValue(20)
    assert "@ 1 patch/strip" in dlg._pace_estimate["i1pro"].text()


def test_the_strip_length_is_remembered(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    from ui.dialogs.settings_dialog import SettingsDialog
    first = SettingsDialog(s)
    first._pace_patches_spin.setValue(24)
    first.accept = lambda: None          # persist without closing a dialog
    first._save_and_close()

    assert int(s.get("pace_estimate_patches", 0)) == 24
    assert SettingsDialog(s)._pace_patches_spin.value() == 24


def test_the_new_spinbox_has_its_own_explanation():
    import inspect

    from ui.dialogs.settings_dialog import SettingsDialog
    src = inspect.getsource(SettingsDialog)
    assert "Patches per strip for the estimate" in src
    # …and it explains the arithmetic, which is the point of the box.
    assert "readings needed" in src or "readings the " in src
