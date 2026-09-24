"""The curated built-in presets: a gear button, a window of ticks, and an arrow
over the rest of each group (Knut, #182 5818659478, beta 42).

*"Users have complained that the current numbers of presets are too many [...]
This would though limit an advanced user to have larger charts available."*
So nothing is removed: the ticked built-ins are listed directly in "Select
preset" and in the Built-in presets list, and the rest of each group waits
under an arrow placed after the group's last ticked preset.

What these tests hold:

* the shipped list (``data/preset_defaults.json``) is exactly what the beta
  rule gives while its ``source`` says it came from the rule, and the rule
  keeps Knut's words (four per instrument group and paper, one to four sheets,
  not the smallest nor the largest);
* a person's choice is stored as their own differences only, so a later
  release that changes the shipped list moves what they never touched and
  nothing they did;
* the pulldown: user presets on top, then per group the ticked ones, an arrow,
  the rest hidden and disabled; the arrow opens by click and by keyboard with
  the list staying open, and it is never selected as a preset;
* the window: ticks in, ticks out, stored on close, kept across a restart;
* the Built-in presets list: the same split, and the same arrow by keyboard;
* the gear button sits between the folder button and the help icon.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings, Qt                          # noqa: E402
from PyQt6.QtTest import QTest                                  # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

import core.curated_presets as cp                               # noqa: E402
from core.argyll_runner import ArgyllRunner                     # noqa: E402
from core.file_manager import FileManager                       # noqa: E402
from core.settings import AppSettings                           # noqa: E402
from ui.tabs.tab_chart import (                                 # noqa: E402
    BUILTIN_PRESET_GROUPS, BUILTIN_PRESET_KEYS, TabChart, builtin_preset_facts,
)

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings(path: Path) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(path), QSettings.Format.IniFormat)
    return s


@pytest.fixture()
def settings(tmp_path):
    s = _settings(tmp_path / "s.ini")
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


@pytest.fixture()
def make_tab(qapp, settings):
    made = []

    def build(s=None):
        t = TabChart(ArgyllRunner(s or settings), FileManager(s or settings),
                     s or settings)
        made.append(t)
        return t
    yield build
    for t in made:
        t.hide()
        t.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# The shipped list and the beta rule
# ---------------------------------------------------------------------------

def _shipped_doc() -> dict:
    return json.loads((ROOT / "data" / "preset_defaults.json")
                      .read_text(encoding="utf-8"))


def test_the_shipped_file_is_what_the_beta_rule_gives():
    doc = _shipped_doc()
    if not doc["source"].startswith("beta rule"):
        pytest.skip("the shipped list now comes from Knut's users' table")
    facts = builtin_preset_facts()
    assert list(doc["shown"]) == cp.beta_selection(facts), (
        "data/preset_defaults.json is not what the beta rule gives; run "
        "python scripts/make_preset_defaults.py")


def test_every_shipped_key_is_a_built_in():
    assert set(_shipped_doc()["shown"]) <= BUILTIN_PRESET_KEYS


def test_the_beta_rule_keeps_knuts_words():
    facts = builtin_preset_facts()
    chosen = set(cp.beta_selection(facts))
    cells: dict = {}
    for f in facts:
        cells.setdefault((f["group"], f["paper"]), []).append(f)
    for cell, rows in cells.items():
        picked = [f for f in rows if f["key"] in chosen]
        assert len(picked) <= 4, cell
        assert all(1 <= f["pages"] <= 4 for f in picked), cell
        if len(rows) > 4:
            counts = sorted(f["patches"] for f in rows)
            smallest = [f for f in rows if f["patches"] == counts[0]]
            largest = [f for f in rows if f["patches"] == counts[-1]]
            assert len(picked) >= 3 or len([
                f for f in rows if 1 <= f["pages"] <= 4]) < 5, cell
            if len(smallest) == 1:
                assert smallest[0]["key"] not in chosen, (cell, "smallest")
            if len(largest) == 1:
                assert largest[0]["key"] not in chosen, (cell, "largest")
    # Every group keeps something to show.
    for heading, entries in BUILTIN_PRESET_GROUPS:
        assert any(k in chosen for _c, _o, k in entries), heading


def test_the_beta_rule_spreads_widths_where_a_paper_has_several():
    """i1Pro on A4 ships 7.5, 8.0 and 8.5 mm charts: the four picks may not
    all be one width."""
    facts = [f for f in builtin_preset_facts()
             if f["group"].startswith("i1Pro /") and f["paper"] == "A4"]
    chosen = set(cp.beta_selection(facts))
    widths = {f["width"] for f in facts if f["key"] in chosen and f["width"]}
    assert len(widths) >= 2, widths


def test_the_facts_read_every_built_in():
    facts = builtin_preset_facts()
    assert len(facts) == len(BUILTIN_PRESET_KEYS)
    assert all(f["paper"] != "?" and f["patches"] > 0 and f["pages"] > 0
               for f in facts)


# ---------------------------------------------------------------------------
# Storing a person's choice
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_defaults(monkeypatch):
    box = {"keys": frozenset({"a", "b"})}
    monkeypatch.setattr(cp, "shipped_defaults", lambda: box["keys"])
    return box


def test_closing_without_a_change_stores_nothing(fake_defaults, settings):
    assert cp.store_choices(settings, {"a", "b"}, ["a", "b", "c"]) is False
    assert not settings.is_stored(cp.SETTING_KEY)
    assert cp.shown_keys(settings, ["a", "b", "c"]) == {"a", "b"}


def test_only_the_differences_are_stored(fake_defaults, settings):
    cp.store_choices(settings, {"a", "c"}, ["a", "b", "c"])
    assert cp.user_choices(settings) == {"b": False, "c": True}
    assert cp.shown_keys(settings, ["a", "b", "c"]) == {"a", "c"}


def test_a_new_release_moves_only_what_the_person_never_touched(
        fake_defaults, settings):
    cp.store_choices(settings, {"a", "c"}, ["a", "b", "c", "d"])
    # The next release ticks b and d, and un-ticks a.
    fake_defaults["keys"] = frozenset({"b", "d"})
    shown = cp.shown_keys(settings, ["a", "b", "c", "d"])
    assert "b" not in shown, "the person un-ticked b; a release may not undo it"
    assert "c" in shown, "the person ticked c"
    assert "d" in shown, "d was never touched, so it follows the release"
    assert "a" not in shown, "a was never touched, so it follows the release"


def test_a_recorded_answer_is_kept_even_when_the_default_agrees(
        fake_defaults, settings):
    cp.store_choices(settings, {"a", "b", "c"}, ["a", "b", "c"])
    fake_defaults["keys"] = frozenset({"a", "b", "c"})
    cp.store_choices(settings, {"a", "b", "c"}, ["a", "b", "c"])
    fake_defaults["keys"] = frozenset({"a", "b"})
    assert "c" in cp.shown_keys(settings, ["a", "b", "c"])


def test_a_corrupt_setting_reads_as_no_choice(settings):
    settings.set(cp.SETTING_KEY, "{not json")
    assert cp.user_choices(settings) == {}


# ---------------------------------------------------------------------------
# The "Select preset" pulldown
# ---------------------------------------------------------------------------

def _arrows(cb) -> list[int]:
    return [r for r in range(cb.count()) if cb.itemData(r, cb.MORE_ROLE)]


def test_the_pulldown_lists_ticked_then_an_arrow_then_the_rest(make_tab):
    tab = make_tab()
    cb = tab._preset_combo
    view = cb.view()
    shown = cp.shown_keys(tab._settings, BUILTIN_PRESET_KEYS)
    assert _arrows(cb), "no arrow row at all"
    for heading, entries in BUILTIN_PRESET_GROUPS:
        top, rest = cp.split_group(entries, shown)
        start = cb.findText(heading)
        assert start > 0, heading
        rows = list(range(start + 1, start + 1 + len(top)))
        assert [cb.itemData(r) for r in rows] == [k for _c, _o, k in top]
        if not rest:
            continue
        arrow = start + 1 + len(top)
        assert cb.itemData(arrow, cb.MORE_ROLE) == heading
        assert cb.itemText(arrow).startswith("▸")
        members = range(arrow + 1, arrow + 1 + len(rest))
        assert [cb.itemData(r) for r in members] == [k for _c, _o, k in rest]
        for r in members:
            assert view.isRowHidden(r), (heading, r)
            assert not cb.model().item(r).isEnabled(), (heading, r)
    # Every built-in is still an entry, so every key resolves.
    for key in BUILTIN_PRESET_KEYS:
        assert cb.findData(key) > 0, key


def test_user_presets_stay_on_top(make_tab, monkeypatch):
    tab = make_tab()
    presets = {"My own chart": {"targen_-f": 400}}
    tab._populate_preset_combo(presets)
    cb = tab._preset_combo
    assert cb.itemData(1) == "My own chart"
    assert not cb.itemText(2)                     # the separator after it


def test_the_arrow_is_disabled_while_the_list_is_closed(make_tab):
    tab = make_tab()
    cb = tab._preset_combo
    arrow = _arrows(cb)[0]
    assert not cb.model().item(arrow).isEnabled()
    cb.showPopup()
    try:
        assert cb.model().item(arrow).isEnabled()
    finally:
        cb.hidePopup()
    assert not cb.model().item(arrow).isEnabled()


def _open_on(cb, row):
    cb.showPopup()
    QApplication.processEvents()
    cb.view().setCurrentIndex(cb.model().index(row, 0))


@pytest.mark.parametrize("key", [Qt.Key.Key_Right, Qt.Key.Key_Return,
                                 Qt.Key.Key_Enter, Qt.Key.Key_Space])
def test_the_keyboard_opens_the_arrow_and_the_list_stays_open(make_tab, key):
    tab = make_tab()
    cb = tab._preset_combo
    view = cb.view()
    arrow = _arrows(cb)[0]
    fired = []
    cb.activated.connect(fired.append)
    before = cb.currentIndex()
    _open_on(cb, arrow)
    try:
        QTest.keyClick(view, key)
        QApplication.processEvents()
        assert cb.itemText(arrow).startswith("▾")
        assert not view.isRowHidden(arrow + 1)
        assert cb.model().item(arrow + 1).isEnabled()
        assert view.window().isVisible(), "the list closed"
        assert view.currentIndex().row() == arrow
        QTest.keyClick(view, Qt.Key.Key_Left)
        QApplication.processEvents()
        assert cb.itemText(arrow).startswith("▸")
        assert view.isRowHidden(arrow + 1)
    finally:
        cb.hidePopup()
    assert fired == [], "an arrow row was chosen like a preset"
    assert cb.currentIndex() == before


def test_left_on_a_revealed_preset_goes_back_up_to_its_arrow(make_tab):
    tab = make_tab()
    cb = tab._preset_combo
    view = cb.view()
    arrow = _arrows(cb)[0]
    _open_on(cb, arrow)
    try:
        QTest.keyClick(view, Qt.Key.Key_Right)
        view.setCurrentIndex(cb.model().index(arrow + 2, 0))
        QTest.keyClick(view, Qt.Key.Key_Left)
        assert view.currentIndex().row() == arrow
    finally:
        cb.hidePopup()


def test_a_click_on_the_arrow_opens_it_and_chooses_nothing(make_tab):
    tab = make_tab()
    cb = tab._preset_combo
    view = cb.view()
    arrow = _arrows(cb)[0]
    fired = []
    cb.activated.connect(fired.append)
    _open_on(cb, 0)
    try:
        rect = view.visualRect(cb.model().index(arrow, 0))
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                         pos=rect.center())
        QApplication.processEvents()
        assert cb.itemText(arrow).startswith("▾")
        assert view.window().isVisible()
    finally:
        cb.hidePopup()
    assert fired == []


def test_the_closed_combo_steps_over_the_arrow_and_the_hidden_rows(make_tab):
    tab = make_tab()
    cb = tab._preset_combo
    arrow = _arrows(cb)[0]
    fired = []
    cb.activated.disconnect()
    cb.activated.connect(fired.append)
    cb.setCurrentIndex(arrow - 1)
    cb.setFocus()
    QTest.keyClick(cb, Qt.Key.Key_Down)
    got = cb.currentIndex()
    assert got > arrow
    assert not cb.itemData(got, cb.MORE_ROLE)
    assert not cb.view().isRowHidden(got), "stepped into a hidden preset"


def test_an_arrow_reaching_the_slot_is_put_back(make_tab):
    tab = make_tab()
    cb = tab._preset_combo
    arrow = _arrows(cb)[0]
    cb.setCurrentIndex(0)
    tab._last_preset_index = 0
    cb.blockSignals(True)
    cb.setCurrentIndex(arrow)
    cb.blockSignals(False)
    tab._on_preset_selected(arrow)
    assert cb.currentIndex() == 0
    assert not cp.is_more_row(cb.currentData())


def test_opening_the_list_on_a_hidden_selection_reveals_its_group(make_tab):
    tab = make_tab()
    cb = tab._preset_combo
    arrow = _arrows(cb)[0]
    member = arrow + 1
    cb.setCurrentIndex(member)
    cb.showPopup()
    try:
        assert not cb.view().isRowHidden(member)
        assert cb.itemText(arrow).startswith("▾")
    finally:
        cb.hidePopup()


# ---------------------------------------------------------------------------
# The window, and a restart
# ---------------------------------------------------------------------------

def test_the_window_stores_the_choice_and_a_restart_keeps_it(
        make_tab, settings, tmp_path, monkeypatch):
    from ui.dialogs.builtin_presets_shown_dialog import BuiltinPresetsShownDialog
    tab = make_tab()
    cb = tab._preset_combo
    shown = cp.shown_keys(settings, BUILTIN_PRESET_KEYS)
    hidden_key = next(k for k in sorted(BUILTIN_PRESET_KEYS) if k not in shown)
    shown_key = next(iter(sorted(shown)))

    def fake_exec(dlg):
        assert dlg.ticked() == shown
        assert dlg.set_ticked(hidden_key, True)
        assert dlg.set_ticked(shown_key, False)
        return 0                                   # Close
    monkeypatch.setattr(BuiltinPresetsShownDialog, "exec", fake_exec)
    tab._open_builtin_presets_shown()

    assert cp.user_choices(settings) == {hidden_key: True, shown_key: False}
    view = cb.view()
    assert not view.isRowHidden(cb.findData(hidden_key))
    assert view.isRowHidden(cb.findData(shown_key))

    # A restart: a fresh store on the same file, a fresh tab.
    settings.sync()
    again = _settings(tmp_path / "s.ini")
    tab2 = make_tab(again)
    cb2 = tab2._preset_combo
    assert not cb2.view().isRowHidden(cb2.findData(hidden_key))
    assert cb2.view().isRowHidden(cb2.findData(shown_key))


def test_the_window_lists_every_built_in_under_the_pulldowns_headings(
        make_tab, qapp):
    from ui.dialogs.builtin_presets_shown_dialog import BuiltinPresetsShownDialog
    tab = make_tab()
    dlg = BuiltinPresetsShownDialog(tab._curated_dialog_groups(), set(), tab)
    try:
        tree = dlg._tree
        assert [tree.topLevelItem(i).text(0)
                for i in range(tree.topLevelItemCount())] == \
            [h for h, _e in BUILTIN_PRESET_GROUPS]
        total = sum(tree.topLevelItem(i).childCount()
                    for i in range(tree.topLevelItemCount()))
        assert total == len(BUILTIN_PRESET_KEYS)
        # A group's own box ticks the whole group.
        g = tree.topLevelItem(0)
        g.setCheckState(0, Qt.CheckState.Checked)
        assert len(dlg.ticked()) == g.childCount()
        assert g.text(1) == f"{g.childCount()} of {g.childCount()} shown"
        # Only a Close button.
        from PyQt6.QtWidgets import QPushButton
        buttons = [b for b in dlg.findChildren(QPushButton) if b.isVisibleTo(dlg)]
        assert len(buttons) == 1
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# The Built-in presets list (the overlay)
# ---------------------------------------------------------------------------

def test_the_overlay_has_the_same_split_and_the_arrow_works_by_keyboard(
        make_tab, monkeypatch):
    from ui.builtin_preset_popup import BuiltinPresetPopup
    tab = make_tab()
    captured = {}
    monkeypatch.setattr(BuiltinPresetPopup, "show_under",
                        lambda self, anchor: captured.setdefault("p", self))
    tab._open_builtin_preset_overlay()
    popup = captured["p"]
    try:
        shown = cp.shown_keys(tab._settings, BUILTIN_PRESET_KEYS)
        items = [r.key for r in popup._rows if r.kind == "item"]
        assert set(items) == shown
        more = [i for i, r in enumerate(popup._rows) if r.kind == "more"]
        assert more
        first = more[0]
        group = popup._rows[first].key
        assert popup._rows[first].text.startswith("▸")
        popup._hover_index = first
        QTest.keyClick(popup, Qt.Key.Key_Right)
        assert popup.is_open(group)
        assert popup._rows[popup._hover_index].kind == "more"
        assert popup._rows[popup._hover_index].text.startswith("▾")
        QTest.keyClick(popup, Qt.Key.Key_Down)
        assert popup._rows[popup._hover_index].group == group
        QTest.keyClick(popup, Qt.Key.Key_Left)
        assert popup._rows[popup._hover_index].kind == "more"
        QTest.keyClick(popup, Qt.Key.Key_Left)
        assert not popup.is_open(group)
        assert set(r.key for r in popup._rows if r.kind == "item") == shown
    finally:
        popup.deleteLater()


# ---------------------------------------------------------------------------
# The gear button
# ---------------------------------------------------------------------------

def test_the_gear_sits_between_the_folder_button_and_the_help_icon(make_tab):
    tab = make_tab()
    gear = tab._preset_shown_btn
    grid = gear.parentWidget().layout()
    # The Presets frame's grid: find it by the reveal button's parent layout.
    from PyQt6.QtWidgets import QGridLayout
    grids = [lay for lay in gear.parentWidget().findChildren(QGridLayout)
             if lay.indexOf(gear) >= 0] or ([grid] if grid else [])
    g = grids[0]
    _r, col_gear, _rs, _cs = g.getItemPosition(g.indexOf(gear))
    _r, col_reveal, _rs, _cs = g.getItemPosition(g.indexOf(tab._preset_reveal_btn))
    assert col_gear == col_reveal + 1
    help_btn = g.itemAtPosition(0, col_gear + 1).widget()
    from ui.tooltip_button import TooltipButton
    assert isinstance(help_btn, TooltipButton)
    assert gear.size() == tab._preset_reveal_btn.size()
    assert gear.property("themed_preset_icon") == "gear"
