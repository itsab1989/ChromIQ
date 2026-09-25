"""K46 (Knut, #182 5834773589, beta 43, B8-1171 to B8-1173).

1. *"The pull-down list for "Select preset" and the "built-in presets" button
   should have a coloured note [...] at the bottom or the top [...] of the
   selection list saying that the list is filtered according to selected paper
   size and to show all paper sizes uncheck "Filter preset-dropdown list
   according to selected paper size" in the "Settings for built-in presets"
   window. When [...] OFF, then the note [...] can say something like "To
   filter this list of built-in presets according to paper size selected,
   enable [...]"."*
2. *"The "Settings for built-in presets" does not have a label defined in the
   tool-tip, I suggest calling it "Settings for built-in presets" [...] All
   places, like help texts, should refer to this label, not general
   descriptions that may be misunderstood."*

What these tests hold:

* both lists end in the note, with the ON text while the filter is on and the
  OFF text while it is off, and it follows a change stored by OK;
* the note is never a choice: disabled and not selectable in "Select preset"
  (so the arrow keys, the wheel and type-ahead step over it, open or closed),
  a click on it is swallowed, the preset handler refuses it; in the Built-in
  presets list it is not in the keyboard's rows, the mouse finds nothing on it
  and it can never be emitted;
* it is painted in the app's information colours for Light, Dark and Neutral,
  the ones the style sheets give ``QLabel#info``;
* the window is called "Settings for built-in presets" (German "Einstellungen
  für integrierte Presets") in its title, the gear's tooltip and accessible
  name, and every text that refers to it; no text calls it anything else.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QEvent, QPoint, QPointF, QSettings, Qt  # noqa: E402
from PyQt6.QtGui import QMouseEvent, QWheelEvent                 # noqa: E402
from PyQt6.QtTest import QTest                                   # noqa: E402
from PyQt6.QtWidgets import QApplication                         # noqa: E402

import core.curated_presets as cp                                # noqa: E402
from core.argyll_runner import ArgyllRunner                      # noqa: E402
from core.file_manager import FileManager                        # noqa: E402
from core.settings import AppSettings                            # noqa: E402
from ui.builtin_preset_popup import BuiltinPresetPopup           # noqa: E402
from ui.tabs.tab_chart import TabChart, preset_list_note         # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NAME = "Settings for built-in presets"
NAME_DE = "Einstellungen für integrierte Presets"
BOX = "Filter preset-dropdown list according to selected paper size"
BOX_DE = "Presetliste im Aufklappmenü nach gewählter Papiergröße filtern"
NOTE_ON = ("This list is filtered by the paper size selected. To show all "
           "paper sizes, untick “Filter preset-dropdown list according to "
           "selected paper size” in “Settings for built-in presets”.")
NOTE_OFF = ("To filter this list of built-in presets by the paper size "
            "selected, tick “Filter preset-dropdown list according to "
            "selected paper size” in “Settings for built-in presets”.")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


@pytest.fixture()
def tab(qapp, settings):
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._populate_preset_combo({"My own preset": {"auto_run": False}})
    yield t
    t._preset_combo.hidePopup()
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _note_rows(cb) -> list[int]:
    return [r for r in range(cb.count()) if cb.itemData(r, cb.NOTE_ROLE)]


def _last_preset_row(cb) -> int:
    return max(r for r in range(cb.count())
               if isinstance(cb.itemData(r), str)
               and not cp.is_not_a_preset(cb.itemData(r))
               and not cb.view().isRowHidden(r)
               and cb.model().item(r).isEnabled())


# ---------------------------------------------------------------------------
# 1. The note
# ---------------------------------------------------------------------------
def test_the_texts_name_the_box_and_the_window():
    assert preset_list_note(True) == NOTE_ON
    assert preset_list_note(False) == NOTE_OFF
    for text in (NOTE_ON, NOTE_OFF):
        assert f"“{BOX}”" in text and f"“{NAME}”" in text
        assert "—" not in text


@pytest.mark.parametrize("on", [True, False])
def test_select_preset_ends_in_the_note_for_the_state(tab, settings, on):
    tab._apply_builtin_presets_shown(
        cp.shown_keys(settings, []) or set(), paper_filter=on)
    cb = tab._preset_combo
    notes = _note_rows(cb)
    assert notes == [cb.count() - 1], "the note is the list's last row"
    row = notes[0]
    assert cb.itemData(row) == cp.NOTE_ROW_DATA
    assert cb.itemText(row) == (NOTE_ON if on else NOTE_OFF)
    assert not cb.view().isRowHidden(row)


def test_the_note_follows_the_box_when_ok_stores_it(tab, settings):
    cb = tab._preset_combo
    assert cp.paper_filter_on(settings)                  # the default is ON
    assert cb.itemText(_note_rows(cb)[0]) == NOTE_ON
    tab._apply_builtin_presets_shown(set(), paper_filter=False)
    assert cb.itemText(_note_rows(cb)[0]) == NOTE_OFF
    tab._apply_builtin_presets_shown(set(), paper_filter=True)
    assert cb.itemText(_note_rows(cb)[0]) == NOTE_ON


def test_the_note_is_disabled_and_not_selectable_open_or_closed(tab, qapp):
    cb = tab._preset_combo
    row = _note_rows(cb)[0]
    flags = cb.model().item(row).flags()
    assert not flags & Qt.ItemFlag.ItemIsEnabled
    assert not flags & Qt.ItemFlag.ItemIsSelectable
    cb.showPopup()
    qapp.processEvents()
    try:
        flags = cb.model().item(row).flags()
        assert not flags & Qt.ItemFlag.ItemIsEnabled, \
            "opening the list must not enable the note, as it does an arrow"
    finally:
        cb.hidePopup()


def test_arrow_keys_wheel_and_type_ahead_never_land_on_the_note(tab, qapp):
    cb = tab._preset_combo
    note = _note_rows(cb)[0]
    last = _last_preset_row(cb)
    # the closed combo: Down and End past the last preset
    cb.setCurrentIndex(last)
    for key in (Qt.Key.Key_Down, Qt.Key.Key_End, Qt.Key.Key_PageDown):
        QTest.keyClick(cb, key)
        assert cb.currentIndex() != note
    # the wheel on the closed combo
    cb.setCurrentIndex(last)
    for _ in range(3):
        ev = QWheelEvent(QPointF(5, 5), QPointF(cb.mapToGlobal(QPoint(5, 5))),
                         QPoint(0, 0), QPoint(0, -120),
                         Qt.MouseButton.NoButton,
                         Qt.KeyboardModifier.NoModifier,
                         Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(cb, ev)
        assert cb.currentIndex() != note
    # type-ahead on the closed combo: the note's own first words
    for words in ("This list", "To filter", "T"):
        cb.setCurrentIndex(last)
        QTest.keyClicks(cb, words)
        assert cb.currentIndex() != note, words
    # the open list: Down from the last preset stays off the note
    cb.setCurrentIndex(last)
    cb.showPopup()
    qapp.processEvents()
    try:
        view = cb.view()
        view.setCurrentIndex(cb.model().index(last, 0))
        for key in (Qt.Key.Key_Down, Qt.Key.Key_End, Qt.Key.Key_PageDown):
            QTest.keyClick(view, key)
            assert view.currentIndex().row() != note
        view.setCurrentIndex(cb.model().index(last, 0))
        view.keyboardSearch("This list")
        assert view.currentIndex().row() != note
    finally:
        cb.hidePopup()
    assert cb.currentIndex() != note


def test_a_click_on_the_note_is_swallowed(tab, qapp):
    cb = tab._preset_combo
    note = _note_rows(cb)[0]
    before = cb.currentIndex()
    cb.showPopup()
    qapp.processEvents()
    try:
        view = cb.view()
        idx = cb.model().index(note, 0)
        view.scrollTo(idx)
        qapp.processEvents()
        pos = view.visualRect(idx).center()
        for et in (QEvent.Type.MouseButtonPress,
                   QEvent.Type.MouseButtonRelease):
            ev = QMouseEvent(et, QPointF(pos),
                             QPointF(view.viewport().mapToGlobal(pos)),
                             Qt.MouseButton.LeftButton,
                             Qt.MouseButton.LeftButton
                             if et == QEvent.Type.MouseButtonPress
                             else Qt.MouseButton.NoButton,
                             Qt.KeyboardModifier.NoModifier)
            assert cb.eventFilter(view.viewport(), ev) is True
    finally:
        cb.hidePopup()
    assert cb.currentIndex() == before


def test_the_preset_handler_refuses_the_note(tab):
    cb = tab._preset_combo
    note = _note_rows(cb)[0]
    before = cb.currentIndex()
    cb.blockSignals(True)
    cb.setCurrentIndex(note)
    cb.blockSignals(False)
    tab._on_preset_selected(note)
    assert cb.currentIndex() == before
    assert not tab._is_deletable_preset(note)
    assert cp.is_not_a_preset(cp.NOTE_ROW_DATA)
    assert not cp.is_not_a_preset("My own preset")


# ---------------------------------------------------------------------------
# The Built-in presets list
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("on", [True, False])
def test_the_built_in_presets_list_ends_in_the_note(tab, settings, qapp, on):
    tab._apply_builtin_presets_shown(set(), paper_filter=on)
    tab._open_builtin_preset_overlay()
    popup = tab._builtin_preset_popup
    try:
        qapp.processEvents()
        rows = popup._rows
        assert rows[-1].kind == "note"
        assert rows[-1].text == (NOTE_ON if on else NOTE_OFF)
        assert [r for r in rows if r.kind == "note"] == [rows[-1]]
    finally:
        popup.close()


def test_the_built_in_presets_list_never_chooses_the_note(qapp):
    groups = [("Group", [("One", "k1"), ("Two", "k2")])]
    popup = BuiltinPresetPopup(groups, None, note=NOTE_ON)
    got: list[str] = []
    popup.selected.connect(got.append)
    try:
        popup.show()
        qapp.processEvents()
        note = len(popup._rows) - 1
        assert popup._rows[note].kind == "note"
        assert note not in popup._selectable()
        # the note is tall enough for its wrapped text
        assert popup._rows[note].height > popup.ROW_H
        # the keyboard: Down past the end stays on the last preset
        for _ in range(6):
            QTest.keyClick(popup, Qt.Key.Key_Down)
            assert popup._hover_index != note
        # the mouse: nothing under it
        centre = popup._row_rect(popup._rows[note]).center()
        popup._scroll_y = popup._max_scroll
        centre = popup._row_rect(popup._rows[note]).center()
        assert popup._index_at(centre) == -1
        # and even asked directly, it is not emitted
        popup._activate(note)
        assert got == []
        assert popup.isVisible(), "the note closed the list as a pick would"
    finally:
        popup.close()


def test_the_note_does_not_widen_the_built_in_presets_list(qapp):
    groups = [("Group", [("One", "k1")])]
    plain = BuiltinPresetPopup(groups, None)
    noted = BuiltinPresetPopup(groups, None, note=NOTE_OFF * 3)
    assert noted.width() == plain.width()
    assert noted.height() > plain.height()


# ---------------------------------------------------------------------------
# The colours
# ---------------------------------------------------------------------------
def _info_rule(sheet: str) -> dict:
    block = re.search(r"QLabel#info\s*\{([^}]*)\}", sheet).group(1)
    out = {}
    for prop in ("background", "color", "border"):
        m = re.search(rf"(?<![-\w]){prop}\s*:\s*([^;]+);", block)
        out[prop] = m.group(1).strip()
    return out


@pytest.mark.parametrize("mode", ["light", "dark", "neutral"])
def test_the_note_is_painted_in_the_info_colours_of_each_appearance(mode):
    from ui.light_styles import LIGHT_STYLESHEET
    from ui.neutral_styles import NEUTRAL_STYLESHEET
    from ui.styles import APP_STYLESHEET
    from ui.theme import info_colours
    sheet = {"light": LIGHT_STYLESHEET, "dark": APP_STYLESHEET,
             "neutral": NEUTRAL_STYLESHEET}[mode]
    rule = _info_rule(sheet)
    c = info_colours(mode)
    assert c["bg"].lower() == rule["background"].lower()
    assert c["text"].lower() == rule["color"].lower()
    assert c["border"].lower() in rule["border"].lower()


def test_both_lists_paint_the_note_through_info_colours():
    import inspect
    import ui.builtin_preset_popup as pop
    import ui.tabs.tab_chart as tc
    assert "info_colours(self._mode)" in inspect.getsource(
        pop.BuiltinPresetPopup._paint_note)
    assert "info_colours()" in inspect.getsource(
        tc._ComboSeparatorDelegate._paint_note)


# ---------------------------------------------------------------------------
# 2. The name
# ---------------------------------------------------------------------------
def test_the_window_title_the_tooltip_and_the_accessible_names(tab, qapp):
    from ui.dialogs.builtin_presets_shown_dialog import (
        BuiltinPresetsShownDialog)
    btn = tab._preset_shown_btn
    assert btn.toolTip().split("\n")[0] == NAME
    assert btn.accessibleName() == NAME
    dlg = BuiltinPresetsShownDialog(tab._curated_dialog_groups(), set(), tab)
    try:
        assert dlg.windowTitle() == NAME
        assert dlg._tree.accessibleName() == NAME
        assert NAME in dlg._help.dialog_body()
        assert NAME in dlg._paper_filter_help.dialog_body()
    finally:
        dlg.deleteLater()


def _catalogue(code: str) -> dict:
    return json.loads((ROOT / "data" / "i18n" / f"{code}.json")
                      .read_text(encoding="utf-8"))


def test_no_text_calls_the_window_anything_else():
    """Every English key: no general description of the window is left."""
    old = ("Built-in presets in the lists", "gear button beside",
           "this window's list", "This window chooses which built-in",
           "the gear window", "built-in presets window",
           "window behind the gear")
    en = _catalogue("de")
    for k in en:
        for words in old:
            assert words not in k, (words, k[:80])


def test_every_text_that_names_the_window_names_it_in_german():
    de = _catalogue("de")
    assert de[NAME] == NAME_DE
    named = [k for k in de if NAME in k]
    # title, tooltip, Manual Presets help, arrow tooltip, the window's two
    # help icons, the two notes
    assert len(named) >= 8, len(named)
    for k in named:
        v = de[k]
        assert NAME_DE in v, k[:60]
        assert "—" not in v or "—" in k, k[:60]
        assert " Sie " not in v and "Ihre " not in v, k[:60]


def test_the_german_notes_name_the_german_box():
    de = _catalogue("de")
    for key in (NOTE_ON, NOTE_OFF):
        assert f"„{BOX_DE}“" in de[key]
        assert f"„{NAME_DE}“" in de[key]
    assert de[BOX] == BOX_DE
