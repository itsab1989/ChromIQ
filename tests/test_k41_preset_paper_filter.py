"""The paper filter in the gear window (Knut, #182 5832303551, beta 43,
B8-1131 to B8-1134).

*"Add a checkbox in the window named "Filter preset-dropdown list according to
selected paper size". When OFF, all presets are listed [...] When ON, the
dropdown lists for "Select preset" and the "built-in presets" button show only
the presets related to the selection in "Paper" field in Create Chart [...]
The presets under headings Scanner are always shown. The Red River Paper
presets area also filtered [...] If the Paper size setting is Custom [...] all
the presets using the Custom Paper size setting will be shown."*

What these tests hold:

* a preset's paper is its printtarg ``-p`` code, every built-in has one, and
  orientation is part of it (A3 Portrait is ``A3``, A3 Landscape ``420x297``);
  any size the Paper field does not name is Custom;
* OFF: the pulldown and the Built-in presets list are exactly what they were;
* ON: only presets on the paper of the mode shown (Guided "Paper size",
  Manual "Paper"), live as the paper or the mode changes; Scanner always;
  a group left empty shows no heading; the arrow counts what it still holds;
  a person's own presets NEVER (Knut, #182 5833232475: "This feature only
  apply build-in presets"; B8-1134 filtered them until then);
* the box is ON by default and a stored OFF is kept (Knut, 5833232475);
* the selected preset stays selected and listed, and every key still
  resolves in the pulldown;
* the box: shown in the window as stored, OK stores it, Close discards it.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings, QTimer                      # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

import core.curated_presets as cp                               # noqa: E402
from core.argyll_runner import ArgyllRunner                     # noqa: E402
from core.file_manager import FileManager                       # noqa: E402
from core.settings import AppSettings                           # noqa: E402
from data.patch_db import PAPER_LABELS                          # noqa: E402
from ui.tabs.tab_chart import (                                 # noqa: E402
    BUILTIN_PRESET_GROUPS, BUILTIN_PRESET_KEYS, PAPER_FILTER_ALWAYS_SHOWN,
    TabChart, builtin_preset_paper, paper_filter_groups,
)

SCANNER = next(h for h, _e in BUILTIN_PRESET_GROUPS if h.startswith("Scanner"))
RED_RIVER = next(h for h, _e in BUILTIN_PRESET_GROUPS if "Red River" in h)
MY_A4 = "My A4 preset"
MY_LETTER = "My Letter preset"
MY_CUSTOM = "My 210x280 preset"
MY_NO_PAPER = "My preset without a paper"
USER_PRESETS = {
    MY_A4: {"printtarg_-p": "A4"},
    MY_LETTER: {"printtarg_-p": "Letter"},
    MY_CUSTOM: {"printtarg_-p": "210x280"},
    MY_NO_PAPER: {"auto_run": False},
}


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
    t._populate_preset_combo(dict(USER_PRESETS))
    yield t
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _listed(tab) -> list:
    """The pulldown's rows as the open list shows them: (text, userData)."""
    cb = tab._preset_combo
    view = cb.view()
    return [(cb.itemText(r), cb.itemData(r)) for r in range(cb.count())
            if not view.isRowHidden(r)]


def _listed_keys(tab) -> set:
    return {d for _t, d in _listed(tab) if isinstance(d, str)
            and not cp.is_more_row(d)}


def _open_all_arrows(tab) -> None:
    tab._open_preset_groups().update(h for h, _e in BUILTIN_PRESET_GROUPS)
    tab._apply_preset_collapse()


def _group_of(key: str) -> str:
    return next(h for h, e in BUILTIN_PRESET_GROUPS
                if any(k == key for _c, _o, k in e))


def _manual_paper(tab, code: str) -> None:
    tab._switch_mode("manual")
    tab._set_manual_value("printtarg", "-p", code)


def _a_builtin_on(paper: str) -> str:
    """A built-in preset laid out on *paper*, outside the Scanner group."""
    return next(k for h, e in BUILTIN_PRESET_GROUPS if h != SCANNER
                for _c, _o, k in e if builtin_preset_paper(k) == paper)


def _filter(settings, on: bool) -> None:
    settings.set(cp.PAPER_FILTER_KEY, on)


# ---------------------------------------------------------------------------
# A preset's paper
# ---------------------------------------------------------------------------

def test_every_built_in_has_a_paper_and_orientation_is_part_of_it():
    for key in BUILTIN_PRESET_KEYS:
        assert builtin_preset_paper(key), key
    assert cp.paper_class("A3") == "A3"
    assert cp.paper_class("420x297") == "420x297"
    assert not cp.paper_matches("A3", "420x297")
    assert cp.paper_matches("A4", "A4")
    assert not cp.paper_matches("A4R", "A4")
    # Any size the Paper field does not name is Custom, whatever it measures.
    assert cp.paper_class("100x150") == cp.CUSTOM_PAPER
    assert cp.paper_class("210x280") == cp.CUSTOM_PAPER
    assert cp.paper_matches("130x180", cp.CUSTOM_PAPER)
    # "4x6" and "11x17" are named papers in inches, not custom millimetres.
    assert cp.paper_class("4x6") == "4x6"
    # No paper: always listed.
    assert cp.paper_matches("", "A4")


def test_scanner_is_the_only_group_never_filtered_and_red_river_is_filtered():
    assert PAPER_FILTER_ALWAYS_SHOWN == {SCANNER}
    groups = dict(paper_filter_groups(BUILTIN_PRESET_GROUPS, "420x297"))
    assert RED_RIVER not in groups          # Red River ships A4 and Letter only
    assert len(groups[SCANNER]) == len(dict(BUILTIN_PRESET_GROUPS)[SCANNER])
    groups = dict(paper_filter_groups(BUILTIN_PRESET_GROUPS, "A4"))
    assert all(builtin_preset_paper(k) == "A4"
               for _c, _o, k in groups[RED_RIVER])
    assert paper_filter_groups(BUILTIN_PRESET_GROUPS, "") \
        is BUILTIN_PRESET_GROUPS


# ---------------------------------------------------------------------------
# The pulldown
# ---------------------------------------------------------------------------

def test_off_the_pulldown_is_what_it_was_whatever_the_paper(tab, settings,
                                                            qapp):
    _filter(settings, False)
    _manual_paper(tab, "A4")
    before = _listed(tab)
    for code in ("420x297", "Letter", "100x150"):
        _manual_paper(tab, code)
        qapp.processEvents()
        assert _listed(tab) == before, code
    tab._switch_mode("guided")
    assert _listed(tab) == before


def test_on_manual_lists_only_the_paper_selected(tab, settings, qapp):
    """MUTATION, proved to land: ``paper_matches`` answering True for every
    preset (red: Letter presets listed on A4)."""
    _filter(settings, True)
    _manual_paper(tab, "A4")
    _open_all_arrows(tab)
    keys = _listed_keys(tab)
    builtins = keys & BUILTIN_PRESET_KEYS
    assert builtins
    for key in builtins:
        assert (_group_of(key) == SCANNER
                or builtin_preset_paper(key) == "A4"), key
    # Every A4 built-in is there, and every Scanner one.
    for heading, entries in BUILTIN_PRESET_GROUPS:
        for _c, _o, key in entries:
            if heading == SCANNER or builtin_preset_paper(key) == "A4":
                assert key in keys, key
    # A person's own presets: never filtered, whatever paper they store
    # (Knut, #182 5833232475). MUTATION: give an own preset its stored paper
    # as PAPER_ROLE again (B8-1134's code) and this goes red.
    assert {MY_A4, MY_LETTER, MY_CUSTOM, MY_NO_PAPER} <= keys


def test_a3_portrait_and_landscape_are_two_papers(tab, settings):
    _filter(settings, True)
    _manual_paper(tab, "A3")
    _open_all_arrows(tab)
    portrait = _listed_keys(tab) & BUILTIN_PRESET_KEYS
    _manual_paper(tab, "420x297")
    landscape = _listed_keys(tab) & BUILTIN_PRESET_KEYS
    scanner = {k for _c, _o, k in dict(BUILTIN_PRESET_GROUPS)[SCANNER]}
    assert portrait - scanner and landscape - scanner
    assert not ((portrait - scanner) & (landscape - scanner))


def test_custom_lists_every_custom_size_preset(tab, settings):
    _filter(settings, True)
    _manual_paper(tab, "150x150")
    assert tab._preset_paper_selected() == cp.CUSTOM_PAPER
    _open_all_arrows(tab)
    keys = _listed_keys(tab)
    custom = {k for k in BUILTIN_PRESET_KEYS
              if builtin_preset_paper(k) not in PAPER_LABELS}
    assert custom and custom <= keys
    for key in keys & BUILTIN_PRESET_KEYS:
        assert key in custom or _group_of(key) == SCANNER, key
    assert {MY_A4, MY_LETTER, MY_CUSTOM, MY_NO_PAPER} <= keys


def test_custom_keeps_the_ticks_and_the_arrow(tab, settings, qapp):
    """Knut, #182 5832436639: on Custom the ticks and the "N more presets"
    arrows still apply, exactly as on any other paper: a custom-size preset
    that is not ticked waits under its group's arrow, not at the top.

    MUTATION, proved to land: a filtered-in preset shown whatever its arrow
    says (red: the unticked one listed with the arrow closed)."""
    _filter(settings, True)
    shown = cp.shown_keys(settings, BUILTIN_PRESET_KEYS)
    custom = [k for k in sorted(BUILTIN_PRESET_KEYS)
              if builtin_preset_paper(k) not in PAPER_LABELS]
    ticked = [k for k in custom if k in shown]
    unticked = [k for k in custom if k not in shown]
    assert ticked and unticked
    _manual_paper(tab, "150x150")
    tab._open_preset_groups().clear()
    tab._apply_preset_collapse()
    cb = tab._preset_combo
    keys = _listed_keys(tab)
    assert set(ticked) <= keys
    assert not (set(unticked) & keys)
    group = _group_of(unticked[0])
    arrow = tab._preset_arrow_row(group)
    assert arrow >= 0 and not cb.view().isRowHidden(arrow)
    waiting = [k for k in unticked if _group_of(k) == group]
    assert cb.itemText(arrow).startswith("▸")
    assert f"{len(waiting)} more preset" in cb.itemText(arrow)
    tab._on_preset_more_row(arrow, "open")
    assert set(waiting) <= _listed_keys(tab)
    assert cb.itemText(arrow).startswith("▾")


def test_an_empty_group_shows_no_heading_and_the_arrow_counts_what_is_left(
        tab, settings):
    """MUTATION, proved to land: headings and separators left alone by the
    filter (red: the CR30 heading stays over nothing on A3 Landscape); the
    arrow's count left at the whole group's (red)."""
    _filter(settings, True)
    _manual_paper(tab, "420x297")
    texts = [t for t, _d in _listed(tab)]
    cr30 = next(h for h, _e in BUILTIN_PRESET_GROUPS if h.startswith("CR30"))
    assert cr30 not in texts
    assert RED_RIVER not in texts
    assert SCANNER in texts
    # No two separators in a row, and none at the end.
    blanks = [i for i, t in enumerate(texts) if t == ""]
    assert all(b + 1 not in blanks for b in blanks)
    cb = tab._preset_combo
    view = cb.view()
    for row in range(cb.count()):
        group = cb.itemData(row, cb.MORE_ROLE)
        if not group or view.isRowHidden(row):
            continue
        # Scanner is never filtered by paper (K41), so its arrow counts every
        # hidden scanner preset; every other group counts only this paper's.
        members = [r for r in range(cb.count())
                   if cb.itemData(r, cb.MEMBER_ROLE) == group
                   and (group == SCANNER
                        or builtin_preset_paper(cb.itemData(r)) == "420x297")]
        assert f"{len(members)} more preset" in cb.itemText(row), group


def test_guided_filters_by_its_own_paper_size_and_the_mode_switch_is_live(
        tab, settings, qapp):
    """MUTATION, proved to land: the filter reading Manual's Paper in both
    modes (red)."""
    _filter(settings, True)
    tab._switch_mode("guided")
    _open_all_arrows(tab)
    # Two different papers in the two modes. (Switching modes carries a
    # changed paper across, Knut #9, so the pages are turned directly here:
    # what is tested is that the list follows the page on screen.)
    tab._set_manual_value("printtarg", "-p", "Letter")
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4"))
    qapp.processEvents()
    assert tab._preset_paper_selected() == "A4"
    a4, letter = _a_builtin_on("A4"), _a_builtin_on("Letter")
    guided = _listed_keys(tab)
    assert a4 in guided and letter not in guided
    tab._stack.setCurrentIndex(1)                     # Manual's page
    qapp.processEvents()
    assert tab._preset_paper_selected() == "Letter"
    manual = _listed_keys(tab)
    assert letter in manual and a4 not in manual
    tab._stack.setCurrentIndex(0)                     # Guided's page
    assert a4 in _listed_keys(tab)
    # Live on Guided's own paper size.
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("Letter"))
    assert letter in _listed_keys(tab) and a4 not in _listed_keys(tab)
    # and a person's own presets in every one of these states
    assert {MY_A4, MY_LETTER} <= _listed_keys(tab)


def test_the_selected_preset_stays_selected_and_listed(tab, settings, qapp):
    """Nothing loaded is ever silently changed: the selection and its row
    stay while the paper moves away from it, and it goes when another is
    chosen. Every key still resolves in the pulldown.

    MUTATION, proved to land: the current row not exempt (red)."""
    _filter(settings, True)
    _manual_paper(tab, "A4")
    cb = tab._preset_combo
    letter = next(k for _c, _o, k in dict(BUILTIN_PRESET_GROUPS)[RED_RIVER]
                  if builtin_preset_paper(k) == "Letter")
    cb.setCurrentIndex(cb.findData(letter))
    _manual_paper(tab, "A4")
    qapp.processEvents()
    assert cb.currentData() == letter
    tab._reveal_current_preset_group()
    assert not cb.view().isRowHidden(cb.currentIndex())
    assert RED_RIVER in [t for t, _d in _listed(tab)]
    for key in BUILTIN_PRESET_KEYS:
        assert cb.findData(key) >= 0, key
    cb.setCurrentIndex(cb.findData(MY_A4))
    tab._reveal_current_preset_group()          # the list opens again
    assert cb.view().isRowHidden(cb.findData(letter))


def test_the_built_in_presets_list_is_filtered_too(tab, settings, qapp):
    _filter(settings, True)
    _manual_paper(tab, "420x297")
    tab._open_builtin_preset_overlay()
    popup = tab._builtin_preset_popup
    try:
        headings = [h for h, _e in popup._groups]
        assert SCANNER in headings and RED_RIVER not in headings
        for heading, entries in popup._groups:
            rest = popup._more.get(heading, [])
            assert entries or rest, heading
            for _label, key in list(entries) + list(rest):
                assert (heading == SCANNER
                        or builtin_preset_paper(key) == "420x297"), key
    finally:
        popup.close()
    _filter(settings, False)
    tab._open_builtin_preset_overlay()
    popup = tab._builtin_preset_popup
    try:
        assert [h for h, _e in popup._groups] == [
            h for h, _e in BUILTIN_PRESET_GROUPS]
    finally:
        popup.close()


# ---------------------------------------------------------------------------
# The box in the window
# ---------------------------------------------------------------------------

def _drive(tab, qapp, *, box: bool, end: str) -> dict:
    done: dict = {}

    def act():
        dlg = tab._builtin_presets_shown_dialog
        if dlg is None or not dlg.isVisible():
            QTimer.singleShot(10, act)
            return
        done["shown_as"] = dlg.paper_filter()
        done["text"] = dlg._paper_filter.text()
        dlg._paper_filter.setChecked(box)
        dog = done["dog"] = QTimer(dlg)
        dog.setSingleShot(True)
        dog.timeout.connect(dlg.reject)
        dog.start(2000)
        (dlg._ok_btn if end == "ok" else dlg._close_btn).click()

    QTimer.singleShot(0, act)
    tab._open_builtin_presets_shown()
    try:
        done["dog"].stop()
    except RuntimeError:        # the window, and its watchdog, are gone
        pass
    qapp.processEvents()
    return done


def test_the_box_is_stored_by_ok_and_discarded_by_close(tab, settings, qapp):
    """MUTATION, proved to land: the box stored whatever ``exec`` returned
    (red on Close); the box not handed to the caller on OK (red)."""
    _manual_paper(tab, "420x297")
    # ON by default (Knut, #182 5833232475: "It should be default ON")
    done = _drive(tab, qapp, box=False, end="close")
    assert done["shown_as"] is True
    assert done["text"] == ("Filter preset-dropdown list according to "
                            "selected paper size")
    assert cp.paper_filter_on(settings) is True
    assert RED_RIVER not in [t for t, _d in _listed(tab)]

    done = _drive(tab, qapp, box=False, end="ok")
    assert cp.paper_filter_on(settings) is False
    assert RED_RIVER in [t for t, _d in _listed(tab)]

    done = _drive(tab, qapp, box=True, end="ok")
    assert done["shown_as"] is False
    assert cp.paper_filter_on(settings) is True
    assert RED_RIVER not in [t for t, _d in _listed(tab)]


def test_the_setting_survives_a_restart(tmp_path, qapp):
    ini = tmp_path / "restart.ini"
    s = AppSettings()
    s._qs = QSettings(str(ini), QSettings.Format.IniFormat)
    # A STORED OFF IS KEPT across a restart, now that ON is the default
    s.set(cp.PAPER_FILTER_KEY, False)
    s._qs.sync()
    s2 = AppSettings()
    s2._qs = QSettings(str(ini), QSettings.Format.IniFormat)
    assert cp.paper_filter_on(s2) is False


def test_the_box_is_on_for_someone_who_never_touched_it(tmp_path, qapp):
    """Knut, #182 5833232475: *"It should be default ON."* MUTATION: the
    default back to False in core/settings.py (red), or in
    ``paper_filter_on`` (red)."""
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "fresh.ini"), QSettings.Format.IniFormat)
    assert cp.paper_filter_on(s) is True


def test_the_german_box_is_translated_by_hand():
    import json
    root = Path(__file__).resolve().parent.parent / "data" / "i18n"
    de = json.loads((root / "de.json").read_text(encoding="utf-8"))
    key = "Filter preset-dropdown list according to selected paper size"
    assert de[key] == ("Presetliste im Aufklappmenü nach gewählter "
                       "Papiergröße filtern")
