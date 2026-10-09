"""Beta 17: Preferences ▸ Measurement's misread tests are ONE TABLE (#182,
Knut 6082015002, the k56 mock-up "prefs_measurement_A_table" approved in
6084176226).

Chart types as columns; each test a bold row with its ON/OFF box left of the
name where it has one; its parameters below, one per row, a box in each
chart-type cell; the same-reading tolerance one merged box; help icons in the
last column; every value saved and read back; it fits in English and in
German at the real dialog width, and on a 13" screen.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QCheckBox, QLabel

from workflow import misread_settings as MS


@pytest.fixture(autouse=True)
def _language_back():
    import core.i18n as i18n
    prev = getattr(i18n, "_language", "en")
    yield
    i18n.set_language(prev)


def _dialog(tmp_path, **stored):
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    for k, v in stored.items():
        s.set(k, v)
    return s, SettingsDialog(s, None)


def _show_measurement(qapp, dlg):
    tabs = dlg._tabs
    i = next(i for i in range(tabs.count())
             if tabs.widget(i).isAncestorOf(dlg._misread_table))
    tabs.setCurrentIndex(i)
    dlg.show()
    for _ in range(5):
        qapp.processEvents()
    return tabs.widget(i)


def _cell(grid, widget):
    for i in range(grid.count()):
        item = grid.itemAt(i)
        w = item.widget()
        if w is not None and (w is widget or w.isAncestorOf(widget)):
            return grid.getItemPosition(i)
    raise AssertionError(widget)


def test_the_layout_is_knuts_table(qapp, tmp_path):
    from ui.dialogs import settings_dialog as sd
    from ui.tooltip_button import TooltipButton
    _s, dlg = _dialog(tmp_path)
    try:
        _show_measurement(qapp, dlg)
        g = dlg._misread_grid
        heads = [dlg._misread_heads[k].text() for k in MS.KINDS]
        assert heads == ["Profiling charts with estimated colours",
                         "Profiling charts made with a pre-conditioning "
                         "profile", "Verification charts",
                         "Calibration charts"]
        # one box per chart type, each in its own column, 1 to 4
        for store in (dlg._patch_limit_spins, dlg._strip_test_checks,
                      dlg._neighbour_limit_spins, dlg._neighbour_radius_spins):
            cols = [_cell(g, store[k])[1] for k in MS.KINDS]
            assert cols == [1, 2, 3, 4]
            rows = {_cell(g, store[k])[0] for k in MS.KINDS}
            assert len(rows) == 1
        # the tests' names in bold; the parameters' not
        names = {w.text(): w for w in dlg._misread_table.findChildren(QLabel)}
        for name in (sd.PATCH_ERROR_LIMIT_NAME, sd.STRIP_TEST_NAME,
                     sd.NEIGHBOUR_CHECK_NAME, sd.SAME_READING_NAME):
            assert f"<b>{name}</b>" in names, name
        for name in (sd.NEIGHBOUR_LIMIT_NAME, sd.NEIGHBOUR_RADIUS_NAME):
            assert name in names, name
        # the neighbour check's switch left of its name, on a row of its own
        # spanning the table, its two parameters below it
        sw = dlg._patch_neighbour_check
        r_sw, _c, _rs, span = _cell(g, sw)
        assert span >= 4
        r_nl = _cell(g, dlg._neighbour_limit_spins["estimated"])[0]
        r_nr = _cell(g, dlg._neighbour_radius_spins["estimated"])[0]
        assert r_nl == r_sw + 1 and r_nr == r_sw + 2
        lbl = names[f"<b>{sd.NEIGHBOUR_CHECK_NAME}</b>"]
        assert sw.mapTo(dlg, sw.rect().topLeft()).x() < \
            lbl.mapTo(dlg, lbl.rect().topLeft()).x()
        # the same-reading tolerance: ONE box across the four columns
        r, c, _rs, span = _cell(g, dlg._same_reading_spin)
        assert (c, span) == (1, 4)
        # a help icon per test, in the last column
        helps = [b for b in dlg._misread_table.findChildren(TooltipButton)]
        assert len(helps) == 4
        assert {_cell(g, b)[1] for b in helps} == {5}
        # no box is a checkbox but the switches
        boxes = dlg._misread_table.findChildren(QCheckBox)
        assert len(boxes) == 5
    finally:
        dlg.close()


def test_the_defaults_show(qapp, tmp_path):
    _s, dlg = _dialog(tmp_path)
    try:
        assert [dlg._patch_limit_spins[k].value() for k in MS.KINDS] == \
            [95, 20, 5, 95]
        assert [dlg._strip_test_checks[k].isChecked() for k in MS.KINDS] == \
            [True, True, False, True]
        assert dlg._patch_neighbour_check.isChecked()
        assert [dlg._neighbour_limit_spins[k].value() for k in MS.KINDS] == \
            [10, 5, 3, 10]
        assert [dlg._neighbour_radius_spins[k].value() for k in MS.KINDS] == \
            [15, 30, 30, 30]
        assert dlg._same_reading_spin.value() == 3.0
        for sp in list(dlg._patch_limit_spins.values()) + [
                dlg._same_reading_spin]:
            assert sp.suffix() == " ΔE*ab"
    finally:
        dlg.close()


def test_every_value_is_saved_and_read_back(qapp, tmp_path):
    from PyQt6.QtWidgets import QDialog
    s, dlg = _dialog(tmp_path)
    try:
        for i, k in enumerate(MS.KINDS):
            dlg._patch_limit_spins[k].setValue(40.0 + i)
            dlg._strip_test_checks[k].setChecked(i % 2 == 1)
            dlg._neighbour_limit_spins[k].setValue(4.0 + i)
            dlg._neighbour_radius_spins[k].setValue(20.0 + i)
        dlg._same_reading_spin.setValue(4.5)
        dlg._patch_neighbour_check.setChecked(False)
        QDialog.accept = lambda self: None
        dlg._save_and_close()
    finally:
        dlg.close()
    for i, k in enumerate(MS.KINDS):
        assert MS.patch_error_limit(s, k) == 40.0 + i
        assert MS.strip_test_on(s, k) is (i % 2 == 1)
        assert MS.neighbour_limit(s, k) == 4.0 + i
        assert MS.neighbour_radius(s, k) == 20.0 + i
    assert MS.same_reading_tolerance(s) == 4.5
    assert MS.neighbour_check_on(s) is False
    _s2, dlg2 = _dialog(tmp_path)
    try:
        dlg2._settings = s
        dlg2._load_misread_table(s)
        assert dlg2._neighbour_radius_spins["calibration"].value() == 23.0
        assert not dlg2._neighbour_limit_spins["estimated"].isEnabled()
    finally:
        dlg2.close()


def test_restore_factory_defaults_restores_the_table(qapp, tmp_path):
    s, dlg = _dialog(tmp_path, patch_neighbour_limit_verification=9.0,
                     patch_strip_test_verification=True)
    try:
        assert dlg._neighbour_limit_spins["verification"].value() == 9.0
        dlg._restore_defaults()
        assert dlg._neighbour_limit_spins["verification"].value() == 3.0
        assert not dlg._strip_test_checks["verification"].isChecked()
    finally:
        dlg.close()


def test_the_help_of_the_strip_test_carries_the_approved_paragraph(qapp):
    from ui.dialogs import settings_dialog as sd
    h = sd.STRIP_TEST_VERIFICATION_HELP
    assert h.startswith("**Strip test on verification charts (off by "
                        "default)**")
    assert "Tukey's fence" in h and "70, 80, 74 and 29" in h
    assert "(Numbers:" not in h and "k56" not in h and "k57" not in h


@pytest.mark.parametrize("lang", ["en", "de"])
def test_it_fits_the_real_dialog_and_a_13_inch_screen(qapp, tmp_path, lang):
    """The table is never what makes the window wider: in English and in
    German its minimum width stays within the Measurement page's own
    minimum (set by the rows that were there before it), it is never
    clipped, and the dialog's minimum fits a 13" MacBook (1280 x 800
    points, the smallest Retina 13"). Measured on screen too (the beta 17
    protocol's photographs)."""
    import core.i18n as i18n
    i18n.set_language(lang)
    _s, dlg = _dialog(tmp_path)
    try:
        page = _show_measurement(qapp, dlg)
        need = dlg._misread_table.minimumSizeHint().width()
        have = dlg._misread_table.width()
        assert need <= have + 1, (lang, need, have)
        content = page.widget()
        outer = dlg._misread_table.parentWidget()
        outer.hide()
        qapp.processEvents()
        without = content.minimumSizeHint().width()
        outer.show()
        assert need <= without, (lang, need, without)
        assert need <= 1280 - 2 * dlg._SCREEN_MARGIN - 80, (lang, need)
        assert dlg.minimumWidth() <= 1280 - 2 * dlg._SCREEN_MARGIN, (
            lang, dlg.minimumWidth())
    finally:
        dlg.close()
