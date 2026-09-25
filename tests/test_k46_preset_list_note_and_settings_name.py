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

* both lists carry the note, with the ON text while the filter is on and the
  OFF text while it is off, and it follows a change stored by OK;
* since B8-1226 (Knut, #182 5839478031) it is PINNED under each list, visible
  with the list scrolled to the top, and the list above still scrolls fully;
* the note is never a choice: it is not an entry of "Select preset" at all,
  and a click on it is swallowed; in the Built-in presets list it is not in
  the keyboard's rows, the mouse finds nothing on it and it is never emitted;
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
    """Rows of the combo that carry the note: none since B8-1226."""
    return [r for r in range(cb.count())
            if cb.itemData(r) == cp.NOTE_ROW_DATA
            or cb.itemText(r) in (NOTE_ON, NOTE_OFF)]


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
def test_select_preset_carries_the_note_for_the_state(tab, settings, on):
    """The note for the state, pinned under the list (B8-1226), and no longer
    an entry of the combo."""
    tab._apply_builtin_presets_shown(
        cp.shown_keys(settings, []) or set(), paper_filter=on)
    cb = tab._preset_combo
    assert cb.note() == (NOTE_ON if on else NOTE_OFF)
    assert _note_rows(cb) == [], "the note is not a row of the list any more"


def test_the_note_follows_the_box_when_ok_stores_it(tab, settings):
    cb = tab._preset_combo
    assert cp.paper_filter_on(settings)                  # the default is ON
    assert cb.note() == NOTE_ON
    tab._apply_builtin_presets_shown(set(), paper_filter=False)
    assert cb.note() == NOTE_OFF
    tab._apply_builtin_presets_shown(set(), paper_filter=True)
    assert cb.note() == NOTE_ON


def _open(cb, qapp):
    cb.showPopup()
    for _ in range(5):
        qapp.processEvents()
    view = cb.view()
    return view, view.window(), cb._note_footer


def test_the_note_is_pinned_under_the_list_scrolled_to_the_top(tab, qapp):
    """Knut, #182 5839478031: *"not visible before scrolling to the bottom.
    Can the message be made to always stay visible at the bottom"*. With the
    list scrolled to the TOP, and to the end, the note is shown, inside the
    popup's frame, under the list, whole. MUTATION: add the footer to nothing
    / hide it (red); make it a row again (red: `_note_rows`)."""
    cb = tab._preset_combo
    view, frame, foot = _open(cb, qapp)
    try:
        assert view.verticalScrollBar().maximum() > 0, \
            "the list is long enough to scroll"
        for where in ("top", "end"):
            bar = view.verticalScrollBar()
            bar.setValue(0 if where == "top" else bar.maximum())
            qapp.processEvents()
            assert foot is not None and foot.isVisible(), where
            assert foot.text() == NOTE_ON
            g = foot.geometry()
            assert frame.rect().contains(g), (where, g, frame.rect())
            assert g.top() >= view.geometry().bottom(), (where, g,
                                                        view.geometry())
            assert g.height() >= foot.heightForWidth(g.width()) - 1
    finally:
        cb.hidePopup()


def test_the_list_above_the_note_still_scrolls_to_its_last_row(tab, qapp):
    """The note takes its own room: the last listed row can still be
    scrolled fully into view above it."""
    cb = tab._preset_combo
    view, _frame, foot = _open(cb, qapp)
    try:
        last = max(r for r in range(cb.count()) if not view.isRowHidden(r))
        idx = cb.model().index(last, 0)
        view.scrollTo(idx)
        qapp.processEvents()
        rect = view.visualRect(idx)
        assert view.viewport().rect().contains(rect), (rect,
                                                       view.viewport().rect())
    finally:
        cb.hidePopup()


def test_the_note_never_widens_the_list(tab, qapp):
    cb = tab._preset_combo
    assert cb._note_footer.sizeHint().width() == 0
    assert cb._note_footer.minimumSizeHint().width() == 0


def test_arrow_keys_wheel_and_type_ahead_never_reach_the_note(tab, qapp):
    """Nothing can step onto the note: it is not an entry of the combo."""
    cb = tab._preset_combo
    last = _last_preset_row(cb)
    cb.setCurrentIndex(last)
    for key in (Qt.Key.Key_Down, Qt.Key.Key_End, Qt.Key.Key_PageDown):
        QTest.keyClick(cb, key)
        assert cb.itemData(cb.currentIndex()) != cp.NOTE_ROW_DATA
    for words in ("This list", "To filter", "T"):
        cb.setCurrentIndex(last)
        QTest.keyClicks(cb, words)
        assert cb.itemText(cb.currentIndex()) not in (NOTE_ON, NOTE_OFF)


def test_a_click_on_the_note_is_swallowed(tab, qapp):
    cb = tab._preset_combo
    before = cb.currentIndex()
    _view, _frame, foot = _open(cb, qapp)
    try:
        pos = foot.rect().center()
        for et in (QEvent.Type.MouseButtonPress,
                   QEvent.Type.MouseButtonRelease):
            ev = QMouseEvent(et, QPointF(pos),
                             QPointF(foot.mapToGlobal(pos)),
                             Qt.MouseButton.LeftButton,
                             Qt.MouseButton.LeftButton
                             if et == QEvent.Type.MouseButtonPress
                             else Qt.MouseButton.NoButton,
                             Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(foot, ev)
            assert ev.isAccepted()
        qapp.processEvents()
    finally:
        cb.hidePopup()
    assert cb.currentIndex() == before


def test_the_preset_handler_still_refuses_the_note_data(tab):
    assert cp.is_not_a_preset(cp.NOTE_ROW_DATA)
    assert not cp.is_not_a_preset("My own preset")


# ---------------------------------------------------------------------------
# The Built-in presets list
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("on", [True, False])
def test_the_built_in_presets_list_carries_the_note(tab, settings, qapp, on):
    tab._apply_builtin_presets_shown(set(), paper_filter=on)
    tab._open_builtin_preset_overlay()
    popup = tab._builtin_preset_popup
    try:
        qapp.processEvents()
        assert popup._note == (NOTE_ON if on else NOTE_OFF)
        assert popup._note_h > popup.ROW_H
        assert all(r.kind != "note" for r in popup._rows)
    finally:
        popup.close()


def test_the_built_in_presets_note_is_pinned_under_the_rows(qapp):
    """B8-1226: scrolled to the top and to the end, the note sits in the same
    place, under the scrolling rows, inside the panel. MUTATION: put it back
    among the rows (red)."""
    groups = [("Group", [(f"Preset {i}", f"k{i}") for i in range(30)])]
    popup = BuiltinPresetPopup(groups, None, note=NOTE_ON)
    try:
        popup.show()
        qapp.processEvents()
        assert popup._max_scroll > 0
        places = []
        for y in (0, popup._max_scroll):
            popup._scroll_y = y
            note = popup._note_rect()
            places.append(note)
            assert popup._panel_rect().contains(note)
            assert note.top() >= popup._viewport_rect().bottom()
        assert places[0] == places[1]
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
        for _ in range(6):
            QTest.keyClick(popup, Qt.Key.Key_Down)
        assert popup._rows[popup._hover_index].kind == "item"
        assert popup._index_at(popup._note_rect().center()) == -1
        QTest.mouseClick(popup, Qt.MouseButton.LeftButton,
                         pos=popup._note_rect().center())
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
        tc._PresetListNote.paintEvent)


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
