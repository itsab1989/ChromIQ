"""4.3.54: "when the dual scan runs" sits IN the dual scan's own row of Preferences > Beta.

The owner (2026-11-20): "i hope the combobox does not need an extra line in the beta section
and fits right within the line of the main option". Pinned in every shipped language, at the
dialog's minimum size: the box is in the checkbox's row, left of the (i); nothing is cut off;
the page is not one pixel taller than without the box; greyed with the checkbox as the other
sub-controls are; and it loads and saves the stored mode.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.helpers.languages import shipped_languages   # noqa: E402
from workflow.dual_scan import session as D             # noqa: E402


class _S(dict):
    def get(self, k, d=None):
        from core.settings import DEFAULTS
        return super().get(k, DEFAULTS.get(k, d))

    def set(self, k, v):
        self[k] = v


@pytest.fixture(autouse=True)
def _back_to_english():
    from core import i18n
    yield
    i18n.set_language("en")


def _dialog(qapp, s):
    from ui.dialogs import settings_dialog as sd
    dlg = sd.SettingsDialog(s, None)
    dlg.resize(dlg.minimumSize())
    dlg.show()
    for i in range(dlg._tabs.count()):
        if dlg._tabs.widget(i).isAncestorOf(dlg._beta_page):
            dlg._tabs.setCurrentIndex(i)
    qapp.processEvents()
    dlg._beta_page.layout().activate()
    qapp.processEvents()
    return dlg


@pytest.mark.parametrize("lang", ["en"] + list(shipped_languages()))
def test_the_box_fits_in_the_row_at_the_minimum_size(qapp, lang):
    from core import i18n
    i18n.set_language(lang)
    dlg = _dialog(qapp, _S({"i1pro3_conditions_beta": True, D.SETTING: True}))
    try:
        cb, combo, tip = dlg._i1pro2_dual_check, dlg._dual_mode_combo, dlg._i1pro2_dual_tip
        page = dlg._beta_page
        assert combo.parentWidget() is cb.parentWidget()
        # the themes pin a "compact_input" box to 22 px; an ordinary Preferences box is 36 px
        # and made the row 14 px taller on screen (measured 2026-11-20, offscreen has no theme)
        assert combo.objectName() == "compact_input"
        assert abs(combo.geometry().center().y() - cb.geometry().center().y()) <= 2, \
            "in the checkbox's row"
        assert cb.width() >= cb.sizeHint().width(), "the label is not cut off"
        assert combo.width() >= combo.sizeHint().width(), "the entries are not cut off"
        assert cb.geometry().right() < combo.geometry().left()
        assert combo.geometry().right() < tip.geometry().left()
        assert tip.geometry().right() <= page.width()
        # the row needs far less than the room the dialog's own floor (1040 px) gives the
        # page, so it never brings a horizontal scroll bar (offscreen the dialog is clamped to
        # a small virtual screen; the bar itself is judged on screen)
        row = cb.parentWidget().layout()
        row_w = next(row.itemAt(i).layout().minimumSize().width()
                     for i in range(row.count())
                     if row.itemAt(i).layout() is not None
                     and row.itemAt(i).layout().indexOf(combo) >= 0)
        assert row_w + 32 <= 1040 - 80, row_w
        # no row moves: every row below stands where it stands without the box (4.3.53's row)
        below = (dlg._dual_model_combo, dlg._dual_model_note, dlg._fd9_support_check)
        ys = [w.geometry().y() for w in below] + [cb.geometry().y(), cb.height()]
        combo.setVisible(False)
        page.layout().activate()
        qapp.processEvents()
        assert [w.geometry().y() for w in below] + [cb.geometry().y(), cb.height()] == ys
    finally:
        dlg.close()
        dlg.deleteLater()


def test_greyed_with_the_checkbox_and_loaded_and_saved(qapp):
    s = _S({"i1pro3_conditions_beta": True, D.SETTING: False, D.MODE_SETTING: "always"})
    dlg = _dialog(qapp, s)
    try:
        combo = dlg._dual_mode_combo
        assert combo.currentData() == "always"
        assert not combo.isEnabled()
        dlg._i1pro2_dual_check.setChecked(True)
        assert combo.isEnabled()
        dlg._i1pro3_conditions_check.setChecked(False)
        assert not combo.isEnabled()
        dlg._i1pro3_conditions_check.setChecked(True)
        combo.setCurrentIndex(combo.findData("m1_m2"))
        assert [combo.itemText(i) for i in range(combo.count())] == [
            "always", "only for M1 or M2"]
        dlg._save_and_close()
        assert s[D.MODE_SETTING] == "m1_m2"
    finally:
        dlg.deleteLater()


def test_the_help_states_the_trade_off():
    from ui.dialogs.settings_dialog import i1pro2_dual_scan_help
    h = i1pro2_dual_scan_help()
    assert "only for M1 or M2" in h and "always" in h
    assert "has no M1 or M2" in h and "measuring the chart again" in h
    assert "GUIDED" in h


# ---- 4.3.54: the i1iO's "Row speed" field, in the row of "Table charts start with -p ticked" ----

@pytest.mark.parametrize("lang", ["en"] + list(shipped_languages()))
def test_the_row_speed_field_fits_in_its_row_at_the_minimum_size(qapp, lang):
    from core import i18n
    i18n.set_language(lang)
    dlg = _dialog(qapp, _S({"i1io_support_beta": True}))
    # the dialog's own floor on a real screen (1040 px; offscreen the virtual screen is smaller
    # and clamps it, which re-wraps the long notes above whatever this row holds)
    dlg.resize(max(1040, dlg.minimumWidth()), dlg.height())
    qapp.processEvents()
    dlg._beta_page.layout().activate()
    qapp.processEvents()
    try:
        cb, lab, spin = dlg._i1io_pbp_check, dlg._i1io_speed_label, dlg._i1io_speed_spin
        tip, pbp_tip = dlg._i1io_speed_tip, dlg._i1io_pbp_tip
        assert spin.objectName() == "compact_input"
        for w in (lab, spin, tip):
            assert abs(w.geometry().center().y() - cb.geometry().center().y()) <= 3, w
        assert cb.width() >= cb.sizeHint().width() and lab.width() >= lab.sizeHint().width()
        assert spin.width() >= spin.sizeHint().width()
        assert cb.geometry().right() < lab.geometry().left() < spin.geometry().left()
        assert tip.geometry().right() < pbp_tip.geometry().left()
        row = cb.parentWidget().layout()
        row_w = next(row.itemAt(i).layout().minimumSize().width()
                     for i in range(row.count())
                     if row.itemAt(i).layout() is not None
                     and row.itemAt(i).layout().indexOf(spin) >= 0)
        assert row_w + 32 <= 1040 - 80, row_w
        below = [w for w in (dlg._isis_charts_check, dlg._i1io_pbp_tip)]
        ys = [w.geometry().y() for w in below] + [cb.geometry().y(), cb.height()]
        for w in (lab, spin, tip):
            w.setVisible(False)
        dlg._beta_page.layout().activate()
        qapp.processEvents()
        assert [w.geometry().y() for w in below] + [cb.geometry().y(), cb.height()] == ys
    finally:
        dlg.close()
        dlg.deleteLater()


def test_the_row_speed_field_is_greyed_with_the_i1io_option_and_saved(qapp):
    s = _S({"i1io_support_beta": False, "i1io_table_row_speed_factor": 1.37})
    dlg = _dialog(qapp, s)
    try:
        spin = dlg._i1io_speed_spin
        assert spin.value() == pytest.approx(1.35)          # on its grid
        assert (spin.minimum(), spin.maximum(), spin.singleStep(), spin.decimals()) == (
            0.5, 2.0, 0.05, 2)
        assert not spin.isEnabled()
        dlg._i1io_support_check.setChecked(True)
        assert spin.isEnabled()
        spin.setValue(1.95)
        dlg._save_and_close()
        assert s["i1io_table_row_speed_factor"] == pytest.approx(1.95)
    finally:
        dlg.deleteLater()


def test_the_row_speed_help_says_the_risk_and_the_numbers():
    from ui.dialogs.settings_dialog import i1io_row_speed_help
    h = i1io_row_speed_help()
    # 4.3.54 release integration: the risk paragraph made true with the row placement check
    # in place (what it catches, what it cannot, "in our tests"), and the help shorter
    for s in ("1.00", "40 and 168 mm/s", "137 to 168 mm/s", "88 mm/s", "132 mm/s",
              "14 mm and longer", "checks every row read as a strip against its own readings",
              "offers to read it again at 1.00", "In our tests", "about 0.5 dE00",
              "one good row in five was refused", "a whole patch off",
              "UV pass of a dual row is placed by timing alone", "one table's recordings",
              "compare a fast measurement once with one at 1.00",
              "until you set it back to 1.00", "measurement file and the app log",
              "Rows read patch by patch are not affected"):
        assert s in h, s
    for s in ("nothing will warn", "may not notice"):     # no longer true with the check
        assert s not in h, s
    assert len(h) < 1500
