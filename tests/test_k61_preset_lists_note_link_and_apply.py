"""K61 (Knut, #182 5851645723, his test of beta 44), four items:

A. B8-1410. *"we also decided that Custom should show all types of presets
   that have selected Custom paper."* With the paper filter on and Manual's
   Paper on "Custom…", both lists show every Custom-paper preset, and when
   the width and height equal a named paper (B8-1310) that paper's presets
   too. A Custom 210 x 297 listed the A4 Portrait presets and no Custom one.
B. B8-1411. The note under both lists ends ", or click here" and the gear of
   the "Settings for built-in presets" button; clicking it opens that window.
C. B8-1412. The window's OK is "Apply & save", the label, key and German of
   the one other window that has it ("Apply a device-link to an image"),
   still the default button.
D. B8-1413. Preferences > Chart Layout's clip-border note keeps only its
   first sentence: *"They are kept while it is off." This part is not
   relevant to know and should be removed.*

Mutations (each run red, `~/Desktop/ChromIQ-beta45-proof/batch1/k61/`):
M61-a `custom_selection` returns the named paper alone; M61-b
`_manual_paper_is_custom_entry` always False; M61-c the note's link words
left out of the anchor (`note_document` without the link); M61-d the popup's
click on the link not handled; M61-e the button labelled OK again; M61-f the
second sentence back in the Preferences note; M61-g the Select preset note
ignoring a release on its link.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QEvent, QPoint, QPointF, QSettings, Qt  # noqa: E402
from PyQt6.QtGui import QMouseEvent                               # noqa: E402
from PyQt6.QtWidgets import QApplication                          # noqa: E402

import core.curated_presets as cp                                 # noqa: E402
import ui.tabs.tab_chart as TC                                    # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("use_chromiq_layout_engine", True)
    return s


@pytest.fixture()
def tab(qapp, settings):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    t = TC.TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    t._manual_engine_check.setChecked(True)
    qapp.processEvents()
    yield t
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _de() -> dict:
    return json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# A. Custom lists every Custom preset
# ---------------------------------------------------------------------------
def test_the_rule_in_one_line():
    assert cp.custom_selection("A4") == "A4|custom"
    assert cp.custom_selection(cp.CUSTOM_PAPER) == cp.CUSTOM_PAPER
    assert cp.custom_selection("") == cp.CUSTOM_PAPER
    assert cp.paper_matches("100x150", "A4|custom")
    assert cp.paper_matches("A4", "A4|custom")
    assert not cp.paper_matches("A3", "A4|custom")
    assert not cp.paper_matches("100x150", "A4")        # a named paper alone


def _custom(tab, qapp, w, h):
    panel = tab._manual_layout_panel
    panel.paper.setCurrentIndex(panel.paper.findData("__custom__"))
    panel.custom_w.setValue(w)
    panel.custom_h.setValue(h)
    qapp.processEvents()


def _listed_papers(tab):
    """The papers of the built-in presets "Select preset" can show now."""
    cb = tab._preset_combo
    tab._apply_preset_collapse()
    out = set()
    for row in range(cb.count()):
        paper = cb.itemData(row, cb.PAPER_ROLE)
        if paper and not cb.view().isRowHidden(row):
            out.add(cp.paper_class(paper))
        # a group whose presets all wait under its arrow is listed by the arrow
    for heading, entries in TC.paper_filter_groups(
            TC.BUILTIN_PRESET_GROUPS, tab._preset_paper_selected()):
        for e in entries:
            out.add(cp.paper_class(TC.builtin_preset_paper(e[-1])))
    return out


def test_custom_210_x_297_lists_a4_portrait_and_every_custom_preset(tab, qapp):
    _custom(tab, qapp, 210, 297)
    assert tab._preset_paper_selected() == "A4|custom"
    papers = _listed_papers(tab)
    assert papers == {"A4", cp.CUSTOM_PAPER}, papers


def test_custom_on_a_size_no_paper_names_lists_the_custom_presets(tab, qapp):
    _custom(tab, qapp, 250, 300)
    assert tab._preset_paper_selected() == cp.CUSTOM_PAPER
    assert _listed_papers(tab) == {cp.CUSTOM_PAPER}


def test_a_named_paper_chosen_as_itself_lists_only_its_own(tab, qapp):
    panel = tab._manual_layout_panel
    panel.paper.setCurrentIndex(panel.paper.findData("A4"))
    qapp.processEvents()
    assert tab._preset_paper_selected() == "A4"
    assert _listed_papers(tab) == {"A4"}


def test_the_built_in_presets_list_is_filtered_the_same_way(tab, qapp):
    _custom(tab, qapp, 210, 297)
    tab._open_builtin_preset_overlay()
    popup = tab._builtin_preset_popup
    try:
        keys = {r.key for r in popup._rows if r.kind == "item"}
        keys |= {k for rest in popup._more.values() for _l, k in rest}
        classes = {cp.paper_class(TC.builtin_preset_paper(k)) for k in keys}
        assert classes == {"A4", cp.CUSTOM_PAPER}, classes
    finally:
        popup.close()


def test_the_help_texts_say_custom_adds_the_named_paper(tab):
    from ui.dialogs.builtin_presets_shown_dialog import (
        BuiltinPresetsShownDialog)
    dlg = BuiltinPresetsShownDialog(tab._curated_dialog_groups(), set(), tab)
    try:
        window, box = dlg._help.dialog_body(), \
            dlg._paper_filter_help.dialog_body()
        assert "that paper's presets are listed too" in window
        assert "that paper's presets are shown too" in box
        for text in (window, box):
            assert "whatever the width and height say" in text
            assert "count as that paper" not in text
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# B. The note's link
# ---------------------------------------------------------------------------
def test_the_note_ends_with_click_here_in_both_states():
    for on in (True, False):
        text = TC.preset_list_note(on)
        assert text.endswith(", or click here"), text
        assert "—" not in text
    de = _de()
    assert de["click here"] == "klicke hier"
    for k in de:
        if k.endswith(", or {click_here}"):
            assert de[k].endswith(", oder {click_here}"), k


def _link_point(widget_contains, on_link, rect):
    for y in range(rect.top(), rect.bottom(), 2):
        for x in range(rect.right(), rect.left(), -2):
            p = QPoint(x, y)
            if widget_contains(p) and on_link(p):
                return p
    return None


def test_the_select_preset_note_opens_the_window(tab, qapp, monkeypatch):
    opened = []
    monkeypatch.setattr(tab, "_open_builtin_presets_shown",
                        lambda: opened.append(True))
    cb = tab._preset_combo
    cb.showPopup()
    for _ in range(5):
        qapp.processEvents()
    foot = cb._note_footer
    try:
        assert foot.isVisible() and foot.link() == "click here"
        pos = _link_point(foot.rect().contains, foot._on_link, foot.rect())
        assert pos is not None, "no point of the note is the link"
        # somewhere that is NOT the link is still swallowed
        assert not foot._on_link(QPoint(foot.rect().left() + 20,
                                        foot.rect().top() + 14))
        for et in (QEvent.Type.MouseButtonPress,
                   QEvent.Type.MouseButtonRelease):
            ev = QMouseEvent(et, QPointF(pos), QPointF(foot.mapToGlobal(pos)),
                             Qt.MouseButton.LeftButton,
                             Qt.MouseButton.LeftButton
                             if et == QEvent.Type.MouseButtonPress
                             else Qt.MouseButton.NoButton,
                             Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(foot, ev)
        for _ in range(5):
            qapp.processEvents()
    finally:
        cb.hidePopup()
    assert opened == [True]
    assert not cb.view().isVisible()


def test_the_built_in_presets_note_opens_the_window(tab, qapp, monkeypatch):
    opened = []
    monkeypatch.setattr(tab, "_open_builtin_presets_shown",
                        lambda: opened.append(True))
    tab._open_builtin_preset_overlay()
    popup = tab._builtin_preset_popup
    got = []
    popup.selected.connect(got.append)
    rect = popup._note_rect()
    pos = _link_point(rect.contains, popup._on_note_link, rect)
    assert pos is not None, "no point of the note is the link"
    from PyQt6.QtTest import QTest
    QTest.mouseClick(popup, Qt.MouseButton.LeftButton, pos=pos)
    for _ in range(5):
        qapp.processEvents()
    assert opened == [True]
    assert got == []
    assert not popup.isVisible()


def test_the_gear_in_the_note_is_the_buttons_gear():
    import inspect
    from ui import preset_note_link as pnl
    src = inspect.getsource(pnl.gear_image)
    assert 'load_folder_twin_icon("gear", "folder_create")' in src
    tab_src = inspect.getsource(TC.TabChart._build_manual_panel) \
        if hasattr(TC.TabChart, "_build_manual_panel") else inspect.getsource(TC)
    assert 'set_folder_twin_icon(self._preset_shown_btn, "gear", "folder_create")' \
        in tab_src


# ---------------------------------------------------------------------------
# C. "Apply & save"
# ---------------------------------------------------------------------------
def test_the_window_accepts_with_apply_and_save(tab, qapp):
    from ui.dialogs.builtin_presets_shown_dialog import (
        BuiltinPresetsShownDialog)
    from core.i18n import tr
    dlg = BuiltinPresetsShownDialog(tab._curated_dialog_groups(), set(), tab)
    try:
        assert dlg._ok_btn.text() == tr("Apply && save")
        assert dlg._ok_btn.isDefault()
        assert _de()["Apply && save"] == "Anwenden && speichern"
        import inspect
        from ui.dialogs import devicelink_apply_dialog as dl
        assert 'tr("Apply && save")' in inspect.getsource(dl)
        for text in (dlg._intro.text(), dlg._help.dialog_body(),
                     dlg._paper_filter_help.dialog_body()):
            assert " OK " not in text and "OK keeps" not in text, text[:80]
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# D. The Preferences note
# ---------------------------------------------------------------------------
def test_the_preferences_note_keeps_its_first_sentence_only(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(clip_content_always_shown=True)
    try:
        assert p._clip_content_note.text() == (
            "These settings apply only when the clip border is On in a "
            "chart layout.")
        assert "kept while" not in p._clip_content_note.text()
        assert _de()[p._clip_content_note.text()] == (
            "Diese Einstellungen gelten nur, wenn der Klemmrand in einem "
            "Chart-Layout auf „An“ steht.")
    finally:
        p.deleteLater()
