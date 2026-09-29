"""B8-1650 to B8-1656: what the 4.3.0 final translation checks found in the code.

* B8-1650: the Create Chart Output label column was cut to the exact rounded
  width of its widest text, and the fractional advance lost the last glyph a
  sliver ("…drukark" in Polish). `_LabelColumnFitter` gives it room.
* B8-1651: Preferences' grey-ramp box showed "560 patches" in every language.
* B8-1652: the on-screen audit never installed Qt's translator, so it reported
  an English "Cancel" the app does not show.
* B8-1653: a Report Limits heading was narrower than its longest word, so the
  Dutch "12647-8:2021" ran into the next heading.
* B8-1656: the CMYK+N card test read the language an earlier test left behind.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ---- B8-1650 ---------------------------------------------------------------
def test_the_label_column_gets_room_past_its_rounded_width(qapp):
    from PyQt6.QtGui import QFontMetricsF
    from PyQt6.QtWidgets import QLabel, QWidget
    from ui.tabs.tab_chart import _LabelColumnFitter

    host = QWidget()
    text = "Nazwa projektu profilu drukarki:"
    lbl = QLabel(text, host)
    other = QLabel("Opis przebiegu 1:", host)
    exact = lbl.fontMetrics().horizontalAdvance(text)
    for w in (lbl, other):
        w.setFixedWidth(exact)              # what the old measure gave
    fitter = _LabelColumnFitter(lbl, [lbl, other], [], lambda: [], exact)
    fitter.refit()
    true_w = QFontMetricsF(lbl.font()).horizontalAdvance(text)
    assert lbl.width() > true_w + 1, (
        f"the column is {lbl.width()} px for text {true_w:.2f} px wide")
    assert other.width() == lbl.width(), "the column's labels drifted apart"


def test_the_fitter_never_narrows_a_column(qapp):
    from PyQt6.QtWidgets import QLabel, QWidget
    from ui.tabs.tab_chart import _LabelColumnFitter

    host = QWidget()
    lbl = QLabel("Short:", host)
    lbl.setFixedWidth(300)
    _LabelColumnFitter(lbl, [lbl], [], lambda: [], 300).refit()
    assert lbl.width() == 300


def test_both_output_columns_carry_a_fitter():
    import ui.tabs.tab_chart as tc
    src = inspect.getsource(tc)
    assert "self._manual_label_fitter = _LabelColumnFitter(" in src
    assert "self._guided_label_fitter = _LabelColumnFitter(" in src


# ---- B8-1651 ---------------------------------------------------------------
def test_the_grey_ramp_suffix_is_translated():
    import ui.dialogs.settings_dialog as sd
    assert 'setSuffix(tr(" patches"))' in inspect.getsource(sd)
    for p in sorted((ROOT / "data" / "i18n").glob("*.json")):
        cat = json.loads(p.read_text(encoding="utf-8"))
        if "@language_name" not in cat:
            continue
        assert cat.get(" patches", " patches") != " patches", (
            f"{p.stem} shows the grey-ramp suffix in English")


# ---- B8-1652 ---------------------------------------------------------------
def test_the_onscreen_audit_translates_qts_own_buttons():
    src = (ROOT / "scripts" / "i18n_onscreen_audit.py").read_text(encoding="utf-8")
    assert src.index("install_qt_translator(app)") > src.index("set_language(")


# ---- B8-1653 ---------------------------------------------------------------
def test_every_report_limits_heading_holds_its_longest_word(qapp):
    import core.i18n as i18n
    from PyQt6.QtGui import QFont, QFontMetrics
    from core.settings import AppSettings
    from ui.dialogs.thresholds_dialog import ThresholdsDialog

    before = i18n._language
    i18n.set_language("nl")
    try:
        dlg = ThresholdsDialog(AppSettings(), None)
        try:
            g = dlg._head_grid
            seen = 0
            for ci in range(2, g.columnCount()):
                item = g.itemAtPosition(0, ci)
                if item is None or item.widget() is None:
                    continue
                hdr = item.widget()
                bold = QFont(hdr.font())
                bold.setBold(True)
                fm = QFontMetrics(bold)
                longest = max(fm.horizontalAdvance(w) for w in hdr.text().split())
                m = hdr.contentsMargins()
                assert hdr.minimumWidth() - m.left() - m.right() >= longest, (
                    f"{hdr.text()!r}: {hdr.minimumWidth()} px holds no "
                    f"{longest} px word")
                assert m.left() > 0, "a heading may touch the one before it"
                seen += 1
            assert seen >= 6
        finally:
            dlg.close()
            dlg.deleteLater()
    finally:
        i18n.set_language(before)


# ---- B8-1656 ---------------------------------------------------------------
def test_the_cmyk_card_test_pins_english():
    src = (ROOT / "tests" / "test_cmyk_n_numbered_list.py").read_text(encoding="utf-8")
    assert '_i18n.set_language("en")' in src


# ---- B8-1654 ---------------------------------------------------------------
def test_ukrainian_names_the_runs_old_folder_as_it_is_on_disk():
    uk = json.loads((ROOT / "data" / "i18n" / "uk.json").read_text(encoding="utf-8"))
    keys = [k for k in uk if k.startswith((
        "No measurements were recorded in that session",
        "Your previous measurement has been moved to the run's old folder"))]
    assert len(keys) == 2
    for k in keys:
        assert "«old»" in uk[k] and "старої папки" not in uk[k], uk[k]
