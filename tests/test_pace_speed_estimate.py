"""#131 (Knut, 2026-07-27): the live "min. strip reading speed" in Preferences.

His original request, in his words: *"Add calculation for each instrument that
updates live based on the values set in 'Readings per second' and 'Minimum
readings per patch' … The calculated xx.y value above calculates live from the
instruments settings and the patches per strip value. User can change the
patches per strip value to see what the minimum speed will become for his
instrument … This way user can customise strip reading speed easily without
having to do calculations."*

**Rewritten for #130, 2026-07-29.** The strip length used to be one box shared
by every instrument. Knut moved it onto each instrument's own row: *"add another
column of input spinboxes with header label 'Patches per strip'. The calculation
for each instruments minimum strip reading speed shall be calculated using the
value in this new per-instrument input, instead of the common input box … (this
common box can be removed)"*.

That is a real correctness change, not cosmetics: strip length follows the
instrument's smallest usable patch, so one number could only ever be right for
one row. The figure has to be right, has to follow all three inputs on its own
row the moment they change, must not follow another row's, and has to say
something sensible for an instrument whose warning is switched off.
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


# ---- the column exists, per instrument, with Knut's numbers -------------
def test_every_instrument_has_its_own_strip_length(dlg):
    from core.measure_pace import MODEL_DEFAULTS
    assert set(dlg._pace_patches) == set(MODEL_DEFAULTS)


def test_the_common_box_is_gone(dlg):
    """His ruling: "this common box can be removed"."""
    assert not hasattr(dlg, "_pace_patches_spin")


@pytest.mark.parametrize("key,patches,minimum", [
    ("i1pro",       25, 20),
    ("i1pro2",      25, 20),
    ("i1pro3",      30, 33),
    ("i1pro3plus",  15, 66),
    ("colormunki",  15, 20),
    ("spectroscan",  0,  0),          # N/A and Off
])
def test_knuts_defaults_are_the_ones_shown(dlg, key, patches, minimum):
    assert dlg._pace_patches[key].value() == patches, key
    assert dlg._pace_min[key].value() == minimum, key


def test_the_spectroscan_reads_as_not_applicable(dlg):
    """A motorised table places its head on each patch in turn, so a strip
    length says nothing about it — and "0" would be a lie dressed as a number."""
    assert dlg._pace_patches["spectroscan"].text() == "N/A"


def test_every_instrument_shows_a_figure(dlg):
    from core.measure_pace import MODEL_DEFAULTS
    assert set(dlg._pace_estimate) == set(MODEL_DEFAULTS)
    for lbl in dlg._pace_estimate.values():
        assert lbl.text().strip()


# ---- the arithmetic ------------------------------------------------------
def test_the_arithmetic_is_the_one_used_while_measuring(dlg):
    """patches × minimum readings ÷ readings per second."""
    dlg._pace_patches["colormunki"].setValue(15)
    dlg._pace_hz["colormunki"].setValue(50)
    dlg._pace_min["colormunki"].setValue(23)

    # 15 × 23 = 345 readings; 345 ÷ 50 = 6.9 s — Knut's own worked example.
    assert "6.9" in dlg._pace_estimate["colormunki"].text()
    assert "15 patches/strip" in dlg._pace_estimate["colormunki"].text()


def test_it_follows_the_readings_per_second(dlg):
    dlg._pace_patches["i1pro"].setValue(20)
    dlg._pace_min["i1pro"].setValue(20)
    dlg._pace_hz["i1pro"].setValue(100)
    assert "4.0" in dlg._pace_estimate["i1pro"].text()

    dlg._pace_hz["i1pro"].setValue(200)
    assert "2.0" in dlg._pace_estimate["i1pro"].text()


def test_it_follows_the_minimum_readings(dlg):
    dlg._pace_patches["i1pro2"].setValue(10)
    dlg._pace_hz["i1pro2"].setValue(200)
    dlg._pace_min["i1pro2"].setValue(20)
    assert "1.0" in dlg._pace_estimate["i1pro2"].text()

    dlg._pace_min["i1pro2"].setValue(40)
    assert "2.0" in dlg._pace_estimate["i1pro2"].text()


def test_it_follows_its_own_strip_length(dlg):
    dlg._pace_hz["colormunki"].setValue(50)
    dlg._pace_min["colormunki"].setValue(23)
    dlg._pace_patches["colormunki"].setValue(11)
    first = dlg._pace_estimate["colormunki"].text()
    dlg._pace_patches["colormunki"].setValue(22)
    second = dlg._pace_estimate["colormunki"].text()
    assert first != second
    assert "5.1" in first and "10.1" in second      # 11 and 22 × 23 ÷ 50


def test_one_rows_strip_length_never_moves_another(dlg):
    """The whole point of the change: these are six independent rows."""
    dlg._pace_hz["i1pro"].setValue(100)
    dlg._pace_min["i1pro"].setValue(20)
    dlg._pace_patches["i1pro"].setValue(20)
    before = dlg._pace_estimate["i1pro"].text()

    dlg._pace_patches["colormunki"].setValue(31)
    assert dlg._pace_estimate["i1pro"].text() == before


def test_the_number_after_the_at_sign_is_that_rows_box(dlg):
    """Knut: "the number behind the @ is equal to the number in the 'Patches per
    strip' input box for that instrument"."""
    for key in ("i1pro", "i1pro2", "i1pro3", "i1pro3plus", "colormunki"):
        dlg._pace_min[key].setValue(20)
        dlg._pace_patches[key].setValue(17)
        assert "@ 17 patches/strip" in dlg._pace_estimate[key].text(), key


def test_an_instrument_with_no_warning_says_so(dlg):
    """The SpectroScan is motorised: there is no swipe to be too quick, and a
    figure of 0.0 seconds would be nonsense."""
    dlg._pace_min["spectroscan"].setValue(0)         # "Off"
    assert dlg._pace_estimate["spectroscan"].text() == "no limit"


def test_a_row_with_no_strip_length_says_so(dlg):
    """Turn the SpectroScan's warning on but leave its strip length at N/A and
    there is still nothing to work out — say that rather than divide by a zero."""
    dlg._pace_min["spectroscan"].setValue(20)
    dlg._pace_patches["spectroscan"].setValue(0)
    assert dlg._pace_estimate["spectroscan"].text() == "not applicable"


def test_the_strip_length_is_singular_for_one_patch(dlg):
    """Never "@ 1 patches/strip"."""
    dlg._pace_patches["i1pro"].setValue(1)
    dlg._pace_hz["i1pro"].setValue(100)
    dlg._pace_min["i1pro"].setValue(20)
    assert "@ 1 patch/strip" in dlg._pace_estimate["i1pro"].text()


# ---- persistence ---------------------------------------------------------
def test_each_strip_length_is_remembered_on_its_own(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    from ui.dialogs.settings_dialog import SettingsDialog
    first = SettingsDialog(s)
    first._pace_patches["i1pro3"].setValue(24)
    first._pace_patches["colormunki"].setValue(12)
    first.accept = lambda: None          # persist without closing a dialog
    first._save_and_close()

    assert int(s.get("pace_estimate_patches_i1pro3", 0)) == 24
    assert int(s.get("pace_estimate_patches_colormunki", 0)) == 12

    again = SettingsDialog(s)
    assert again._pace_patches["i1pro3"].value() == 24
    assert again._pace_patches["colormunki"].value() == 12
    assert again._pace_patches["i1pro2"].value() == 25       # untouched


# ---- the explanation moved into each instrument's ⓘ ----------------------
@pytest.mark.parametrize("key", ["i1pro", "i1pro2", "i1pro3", "i1pro3plus",
                                 "colormunki", "spectroscan"])
def test_each_instrument_explains_all_three_of_its_numbers(key):
    """Knut: "the information in the help icon text for this common parameter
    should then be added to each of the instruments help text icon, informing in
    the text how each of the three calculation values are used"."""
    from core.measure_pace import explanation_for
    _title, body = explanation_for(key)
    assert "patches per strip" in body.lower(), key
    assert "readings per second" in body.lower(), key
    assert "minimum readings per patch" in body.lower(), key
    assert "÷" in body and "×" in body, key


def test_the_worked_figures_in_the_help_match_the_defaults():
    """The ⓘ walks through the arithmetic with the row's own defaults, so a
    changed default can never leave a stale sum behind."""
    from core.measure_pace import (defaults_for, estimate_patches_for,
                                   explanation_for)
    for key in ("i1pro", "i1pro2", "i1pro3", "i1pro3plus", "colormunki"):
        hz, minimum = defaults_for(key)
        patches = estimate_patches_for(key)
        _title, body = explanation_for(key)
        assert f"{patches} × {minimum} = {patches * minimum}" in body, key
        assert f"{patches * minimum} ÷ {int(hz)} = " \
               f"{patches * minimum / hz:.1f} seconds" in body, key
