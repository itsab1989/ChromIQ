"""Beta 15, the last fixes after the on-screen sweep (2026-10-08).

1. "Which presets can be used for verification?": beta 15's second count
   column and the note box over the list left the Preset column 400 px in
   English and 333 in German (543 in beta 14), and the list 14 rows tall
   where beta 14 showed 21. Measured on screen, 1179 x 730 (Knut's size,
   unchanged): 125 of 189 names cut in English, 161 in German, against 17 in
   beta 14. Now the headings are short ("Own colours", "From Profile Gamut",
   each on two lines), the cells hold "16 of 18", the figure columns are as
   wide as what they hold, and the note is one line beside "Sort by" with the
   whole explanation as its tooltip. MUTATIONS: the old two-line "Metrics
   answered, ..." headings or fixed 140 px columns (the name column falls
   below 60 % of the list); the note back in a box over the list (the list
   loses its rows).
2. The main window's minimum width followed its own width: the tab bar's
   minimum tab size was the tab widget's width divided by five, so a window
   at 1470 (a 13" MacBook Air) could never be narrower than 1474. MUTATION:
   remove `SpectrumTabBar.minimumTabSizeHint`.
3. M-PRINT-PAPER-PROFILE-UNKNOWN shows its title: in
   `test_printer_paper_tables.py::test_unknown_model_window_offers_the_dialog`.
4. The Ukrainian credits said "Створено" ("Created by") for "Made possible
   by"; every language's rendering of that part is pinned here.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QLabel, QTabWidget, QWidget

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# -- 2. the main window's minimum width ------------------------------------
def test_the_tab_bar_minimum_does_not_follow_the_window_width(qapp):
    from core.i18n import tr
    from ui.spectrum_tab_bar import SpectrumTabBar
    tabs = QTabWidget()
    tabs.setTabBar(SpectrumTabBar(tabs))
    for name in ("1. Create Chart", "2. Print Chart", "3. Measure",
                 "4. Build Profile", "5. Check & Refine"):
        tabs.addTab(QWidget(), tr(name))
    try:
        tabs.resize(1470, 800)
        tabs.show()
        qapp.processEvents()
        at_1470 = tabs.minimumSizeHint().width()
        tabs.resize(1700, 800)
        qapp.processEvents()
        at_1700 = tabs.minimumSizeHint().width()
        # a 13" MacBook Air is 1470 points wide; the window needs room for
        # its frame
        assert at_1470 <= 1440, at_1470
        assert at_1700 == at_1470, (at_1470, at_1700)
    finally:
        tabs.close()
        tabs.deleteLater()


# -- 1. the presets window ---------------------------------------------------
@pytest.fixture(scope="module")
def dlg(qapp, tmp_path_factory):
    from core.settings import AppSettings
    from ui.dialogs import preset_verification_dialog as PVD
    from ui.tabs.tab_chart import verification_preset_rows
    settings = AppSettings()
    settings._qs = QSettings(str(tmp_path_factory.mktemp("s") / "s.ini"),
                             QSettings.Format.IniFormat)
    d = PVD.PresetVerificationDialog(list(verification_preset_rows(settings)),
                                     None, None)
    d.show()
    qapp.processEvents()
    assert d.wait_for_layouts(120.0)
    qapp.processEvents()
    yield d
    d.close()
    d.deleteLater()


def _preset_items(tree):
    it = tree.topLevelItem(0)
    while it is not None:
        if it.parent() is not None:
            yield it
        it = tree.itemBelow(it)


def test_the_count_headings_are_short(dlg):
    from ui.dialogs import preset_verification_dialog as PVD
    head = dlg._tree.headerItem()
    assert head.text(3) == "Own\ncolours"
    assert head.text(4) == "From Profile\nGamut"
    assert PVD.two_line_heading("Aus dem Profil-Gamut") == "Aus dem\nProfil-Gamut"
    assert PVD.two_line_heading("自有颜色") == "自有颜色"
    # what they count is said once, and in full in the tooltips
    assert head.toolTip(3) == PVD.TWO_COUNTS_NOTE
    assert head.toolTip(4) == PVD.TWO_COUNTS_NOTE
    cells = {it.text(3) for it in _preset_items(dlg._tree)}
    assert "16 of 18" in cells, sorted(cells)[:5]


def test_the_preset_names_keep_their_width(dlg):
    tree = dlg._tree
    assert (dlg.width(), dlg.height()) == (1179, 730)
    widths = [tree.columnWidth(c) for c in range(5)]
    total = sum(widths)
    assert widths[0] >= 0.6 * total, widths
    for c in (3, 4):
        assert widths[c] <= 110, widths


def test_the_note_is_one_line_beside_sort_by_not_a_box_over_the_list(dlg):
    from ui.dialogs import preset_verification_dialog as PVD
    boxes = [lab for lab in dlg.findChildren(QLabel)
             if lab.text() == PVD.TWO_COUNTS_NOTE]
    assert not boxes, "the four-line note is back over the list"
    line = dlg._two_counts
    assert line.text() == PVD.TWO_COUNTS_LINE
    assert line.toolTip() == PVD.TWO_COUNTS_NOTE
    combo = dlg._sort_combo
    assert abs(line.geometry().center().y() - combo.geometry().center().y()) <= 12
    # and the list has the height the box used to take
    assert dlg._tree.height() >= 0.52 * dlg.height(), (
        dlg._tree.height(), dlg.height())


def test_every_preset_name_has_its_whole_name_as_tooltip(dlg):
    from PyQt6.QtCore import Qt
    n = 0
    for it in _preset_items(dlg._tree):
        row = it.data(0, Qt.ItemDataRole.UserRole)
        assert it.toolTip(0) == row.label
        assert it.toolTip(3) == it.text(3)
        n += 1
    assert n > 100


# -- 4. the credits line in every language -----------------------------------
CREDITS = ("Built on ArgyllCMS by Graeme Gill · Made possible by Knut Georg "
           "Larsson · Testing & feedback: Nelson (Pharmacist), Alan Goldhammer")

#: the "Made possible by" part, read in each language (2026-10-08)
MADE_POSSIBLE = {
    "de": "Ermöglicht durch Knut Georg Larsson",
    "es": "Hecho posible por Knut Georg Larsson",
    "fr": "Rendu possible par Knut Georg Larsson",
    "it": "Reso possibile da Knut Georg Larsson",
    "ja": "Knut Georg Larsson の協力により実現",
    "nl": "Mogelijk gemaakt door Knut Georg Larsson",
    "no": "Muliggjort av Knut Georg Larsson",
    "pl": "Umożliwione przez Knuta Georga Larssona",
    "pt": "Tornado possível por Knut Georg Larsson",
    "ru": "Стало возможным благодаря Кнуту Георгу Ларссону",
    "sv": "Möjliggjort av Knut Georg Larsson",
    "uk": "Стало можливим завдяки Knut Georg Larsson",
    "zh_CN": "感谢Knut Georg Larsson让一切成为可能",
}


@pytest.mark.parametrize("lang", sorted(MADE_POSSIBLE))
def test_the_credits_say_made_possible_by(lang):
    cat = json.loads((ROOT / "data" / "i18n" / f"{lang}.json").read_text(
        encoding="utf-8"))
    parts = [p.strip() for p in cat[CREDITS].split("·")]
    assert parts[1] == MADE_POSSIBLE[lang]
    # "Створено" is "created"; nobody created ChromIQ's credits twice
    assert not parts[1].startswith("Створено")
