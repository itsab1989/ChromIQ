"""B8-1221 to B8-1224: the paper filter reads the Paper field ON SCREEN
(Knut, #182 5838170697 to 5838625234, beta 43).

Knut, with the filter on, Manual, A4 and no project: *"only i1Pro and
colormunki heading [...] but not the other instruments"*; on Custom, *"all
presets with a custom size is not showing"*; after 4 x 6 in, A3 presets. With a
project loaded, *"it seems to work"*.

THE CAUSE. With the ChromIQ layout engine on (the default, and Knut's),
Manual's Paper field on screen is the LAYOUT PANEL'S. printtarg's own ``-p``
widget is hidden, and the filter read that hidden widget
(``_preset_paper_selected``). The two are kept in step by
``_sync_manual_selection_from_panel`` only when a person picks a named paper:

* not while the panel loads a recipe (``_loading``): at start-up from the
  saved "Save as Defaults" recipe (Knut's log: ``_init_manual_layout_panel``'s
  first branch), and every time a preset is applied;
* not for Custom: it wrote ``"__custom__"``, which ``-p`` cannot take, so ``-p``
  kept the paper before.

A loaded project happened to work because its chart was laid out by printtarg:
the engine went off and ``-p`` was the field on screen.

The coordinator could not reproduce any of it from a bare TabChart because the
tests of the filter (K41, K42) set ``-p`` directly: the hidden field. They now
choose the paper where a person does (``choose_manual_paper``).

These tests fail on the beta 43 code (proved by reverting
``_manual_paper_on_screen`` to read ``-p``: red), and the last one is a
MainWindow built on Knut's saved settings, because that is where the first
case begins.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

import core.curated_presets as cp                               # noqa: E402
from ui.tabs import tab_chart as TC                             # noqa: E402

SCANNER = next(h for h, _e in TC.BUILTIN_PRESET_GROUPS if h == "Scanner")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set(cp.PAPER_FILTER_KEY, True)
    return s


@pytest.fixture()
def tab(qapp, settings):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    t = TC.TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    qapp.processEvents()
    yield t
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _engine_shown(tab) -> bool:
    return not tab._manual_layout_grp.isHidden()


def _panel_paper(tab, code: str, dims=None) -> None:
    """A person's click in the layout panel's Paper field."""
    panel = tab._manual_layout_panel
    if dims:
        panel.custom_w.setValue(dims[0])
        panel.custom_h.setValue(dims[1])
    panel.paper.setCurrentIndex(panel.paper.findData(code))


def _closed_rows_of(paper: str, tab) -> list:
    """The ticked built-in rows on *paper* (outside Scanner), whose hidden
    state is what the closed pulldown's arrow keys and wheel step through."""
    cb = tab._preset_combo
    return [r for r in range(cb.count())
            if cb.itemData(r) in TC.BUILTIN_PRESET_KEYS
            and cb.itemData(r, cb.GROUP_ROLE) != SCANNER
            and TC.builtin_preset_paper(cb.itemData(r)) == paper
            and not cb.itemData(r, cb.MEMBER_ROLE)
            and r != cb.currentIndex()]


def _groups_listed(tab) -> list:
    """The headings "Select preset" shows, as the open list shows them."""
    tab._reveal_current_preset_group()
    cb = tab._preset_combo
    view = cb.view()
    heads = {h for h, _e in TC.BUILTIN_PRESET_GROUPS}
    return [cb.itemText(r) for r in range(cb.count())
            if not view.isRowHidden(r) and cb.itemText(r) in heads
            and cb.itemData(r) is None]


def _popup_groups(tab) -> list:
    tab._open_builtin_preset_overlay()
    pop = tab._builtin_preset_popup
    heads = [h for h, _e in pop._groups]
    pop.close()
    return heads


def _groups_on(paper: str) -> list:
    return [h for h, e in TC.BUILTIN_PRESET_GROUPS
            if h == SCANNER or any(cp.paper_matches(TC.builtin_preset_paper(k),
                                                   paper) for *_x, k in e)]


def test_manual_with_the_engine_reads_the_layout_panels_paper(tab, qapp):
    """The engine's panel says A3 and the hidden -p says A4: both lists follow
    the panel, the field on screen. MUTATION: read -p again (red: the A4
    groups, i1Pro, CR30 and Red River, are listed)."""
    assert _engine_shown(tab), "the engine is on by default"
    tab._set_manual_value("printtarg", "-p", "A4")
    tab._syncing_manual_sel = True          # as a recipe load leaves them
    try:
        _panel_paper(tab, "A3")
    finally:
        tab._syncing_manual_sel = False
    qapp.processEvents()
    assert tab._manual_paper_pw.get_raw_value() == "A4"
    assert tab._preset_paper_selected() == "A3"
    assert _groups_listed(tab) == _groups_on("A3")
    assert _popup_groups(tab) == _groups_on("A3")


def test_custom_in_the_layout_panel_lists_the_custom_size_presets(tab, qapp):
    """Knut, 5838498921: *"When paper is set to Custom, then all presets with
    a custom size is not showing"*. Either half of the fix alone mends this
    one, so the mutation that proves it is BOTH reverted, which is the beta 43
    code: the filter reading -p and -p left on the paper before, 5 x 7 in,
    which lists Scanner only (red)."""
    _panel_paper(tab, "127x178")
    qapp.processEvents()
    _panel_paper(tab, "__custom__", (100, 150))
    qapp.processEvents()
    assert tab._preset_paper_selected() == cp.CUSTOM_PAPER
    assert _groups_listed(tab) == _groups_on(cp.CUSTOM_PAPER)
    assert _popup_groups(tab) == _groups_on(cp.CUSTOM_PAPER)
    assert "i1Pro / i1Pro 2 / i1Pro 3" in _groups_listed(tab)


def test_custom_reaches_printtargs_paper_too(tab, qapp):
    """The panel's Custom reaches -p as its W x H, not as the "__custom__"
    sentinel -p cannot take (which left -p on the paper before, so Save as
    Defaults stored that and switching the engine off showed it).
    MUTATION: sync ``paper.currentData()`` again (red: -p stays 127x178)."""
    _panel_paper(tab, "127x178")
    qapp.processEvents()
    assert tab._manual_paper_pw.get_raw_value() == "127x178"
    _panel_paper(tab, "__custom__", (130, 180))
    qapp.processEvents()
    assert tab._manual_paper_pw.get_raw_value() == "130x180"
    tab._manual_layout_panel.custom_w.setValue(120)
    qapp.processEvents()
    assert tab._manual_paper_pw.get_raw_value() == "120x180"


def test_a_recipe_loaded_into_the_panel_moves_the_lists(tab, qapp):
    """A preset and the saved defaults load a RECIPE into the panel, with
    its sync to -p off. Knut's log shows exactly that at start-up and on every
    preset. MUTATION: read -p (red: A4's groups stay after an A3 recipe)."""
    from workflow.layout_engine.presets import default_recipe
    _panel_paper(tab, "A4")
    qapp.processEvents()
    tab._set_engine_recipe(default_recipe("CM", "A3"))
    qapp.processEvents()
    assert tab._manual_layout_panel.selection()[1] == "A3"
    assert tab._preset_paper_selected() == "A3"
    # LIVE, not only when a list opens: the closed pulldown's rows are what
    # the arrow keys and the wheel step through.
    cb = tab._preset_combo
    view = cb.view()
    a4_rows = [r for r in range(cb.count())
               if cb.itemData(r) in TC.BUILTIN_PRESET_KEYS
               and TC.builtin_preset_paper(cb.itemData(r)) == "A4"
               and not cb.itemData(r, cb.MEMBER_ROLE)]
    assert a4_rows and all(view.isRowHidden(r) for r in a4_rows)


def test_the_engine_switched_off_hands_the_filter_to_printtargs_paper(
        tab, qapp):
    """Engine off: printtarg's Paper is the field on screen (the toggle
    carries the panel's paper across to it) and the lists follow it at once,
    in the closed pulldown too. MUTATION: read the panel whatever the engine
    (red)."""
    _panel_paper(tab, "A4")
    qapp.processEvents()
    tab._manual_engine_check.setChecked(False)
    qapp.processEvents()
    assert not _engine_shown(tab)
    assert tab._manual_paper_pw.get_raw_value() == "A4"
    tab._set_manual_value("printtarg", "-p", "420x297")
    qapp.processEvents()
    assert tab._preset_paper_selected() == "420x297"
    # LIVE, in the closed pulldown, before any list is opened.
    assert _closed_rows_of("A4", tab) and all(
        tab._preset_combo.view().isRowHidden(r)
        for r in _closed_rows_of("A4", tab))
    assert _groups_listed(tab) == _groups_on("420x297")
    tab._manual_engine_check.setChecked(True)
    qapp.processEvents()
    assert _engine_shown(tab)
    assert tab._preset_paper_selected() == cp.paper_class(
        tab._manual_layout_panel.selection()[1])


def test_a_refused_preset_leaves_no_row_of_its_own_paper_behind(tab, qapp):
    """The selected row is never filtered; when a selection does not take,
    the pulldown goes back, and the row it had exempted must be filtered
    again. MUTATION: no re-collapse in ``_revert_preset_combo`` (red: the
    Letter preset stays in a list filtered to A4)."""
    _panel_paper(tab, "A4")
    qapp.processEvents()
    cb = tab._preset_combo
    letter = next(k for h, e in TC.BUILTIN_PRESET_GROUPS if h != SCANNER
                  for *_x, k in e if TC.builtin_preset_paper(k) == "Letter"
                  and k in cp.shown_keys(tab._settings, TC.BUILTIN_PRESET_KEYS))
    row = cb.findData(letter)
    cb.blockSignals(True)
    cb.setCurrentIndex(row)
    cb.blockSignals(False)
    tab._apply_preset_collapse()
    assert not cb.view().isRowHidden(row)
    tab._revert_preset_combo(to_none=True)
    assert cb.currentIndex() == 0
    assert cb.view().isRowHidden(row)


def test_knuts_start_then_a_preset_on_another_paper(qapp):
    """THE MAINWINDOW, as Knut starts it: Manual, ColorMunki, the engine on,
    a "Save as Defaults" recipe on A4, printtarg's hidden paper saved on A3
    Landscape, no project.

    The start itself comes out right (measured on screen too: the start-up
    puts -p in step), so the first half pins that it stays so. Then the path
    that DOES go wrong, measured on screen: the paper on A3 Landscape, and a
    preset's A4 recipe loaded into the panel, as `_apply_knut_preset` does.
    Beta 43 then listed A3 Landscape's groups under an A4 field: i1Pro,
    ColorMunki and Scanner, which is Knut's *"only i1Pro and colormunki
    heading"*. MUTATION: read -p (red)."""
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    from workflow.layout_engine.presets import default_recipe
    s = AppSettings()
    keys = {"chart_mode": "manual", "chart_instrument": "CM",
            "use_chromiq_layout_engine": True,
            "manual_printtarg_-i_l": "CM",
            "manual_engine_recipe": default_recipe("CM", "A4").to_dict(),
            "manual_printtarg_-p_l": "420x297",
            cp.PAPER_FILTER_KEY: True}
    before = {k: s.get(k) for k in keys}
    for k, v in keys.items():
        s.set(k, v)
    win = None
    try:
        win = MainWindow(s)
        qapp.processEvents()
        tab = win._tab_chart
        assert tab._mode_name() == "manual"
        assert _engine_shown(tab)
        assert tab._manual_layout_panel.selection()[1] == "A4"
        assert tab._preset_paper_selected() == "A4"
        assert _groups_listed(tab) == _groups_on("A4")
        assert _popup_groups(tab) == _groups_on("A4")
        assert "i1Pro 3 Plus" in _groups_listed(tab)
        assert "CR30 (ChnSpec)" in _groups_listed(tab)
        # A3 Landscape by hand, then a preset's A4 recipe.
        _panel_paper(tab, "420x297")
        qapp.processEvents()
        assert _groups_listed(tab) == _groups_on("420x297")
        tab._set_engine_recipe(default_recipe("CM", "A4"))
        qapp.processEvents()
        assert tab._manual_layout_panel.selection()[1] == "A4"
        assert _groups_listed(tab) == _groups_on("A4")
        assert _popup_groups(tab) == _groups_on("A4")
    finally:
        if win is not None:
            win.close()
            win.deleteLater()
            qapp.processEvents()
        for k, v in before.items():
            if v is None:
                s._qs.remove(k)
            else:
                s.set(k, v)


# ---------------------------------------------------------------------------
# B8-1227: Knut's workaround rule (#182 5839418461)
# ---------------------------------------------------------------------------
CM = "ColorMunki / i1Studio / ColorChecker Studio"
I1 = "i1Pro / i1Pro 2 / i1Pro 3"


def _on_paper(group: str, paper: str) -> list:
    return [k for h, e in TC.BUILTIN_PRESET_GROUPS if h == group
            for *_x, k in e
            if cp.paper_matches(TC.builtin_preset_paper(k), paper)]


def test_a_group_with_none_ticked_on_the_paper_lists_them_directly(tab, qapp):
    """Knut: *"if nothing is shown of a selected paper, but presets for that
    paper does exist, then they should show in the preset list, even if they
    were not specified as default"*. On A3 Landscape none of ColorMunki's 8
    presets is ticked by default: both lists show all 8 directly, with no
    arrow; i1Pro, which has ticked ones there, keeps its arrow.
    MUTATION: drop the rule from `_apply_preset_collapse` (red: pulldown) or
    from `_open_builtin_preset_overlay` (red: popup)."""
    shown = cp.shown_keys(tab._settings, TC.BUILTIN_PRESET_KEYS)
    cm = _on_paper(CM, "420x297")
    assert cm and not set(cm) & shown, "the case: none of them ticked"
    i1 = _on_paper(I1, "420x297")
    assert set(i1) & shown and set(i1) - shown
    _panel_paper(tab, "420x297")
    qapp.processEvents()
    cb = tab._preset_combo
    view = cb.view()
    # the closed pulldown, and then the open one
    for opened in (False, True):
        if opened:
            tab._reveal_current_preset_group()
        for k in cm:
            assert not view.isRowHidden(cb.findData(k)), (opened, k)
        arrow = tab._preset_arrow_row(CM)
        assert arrow < 0 or view.isRowHidden(arrow)
        i1_arrow = tab._preset_arrow_row(I1)
        assert not view.isRowHidden(i1_arrow)
        assert cb.itemData(i1_arrow, TC.Qt.ItemDataRole.UserRole + 44) \
            == len(set(i1) - shown)
    tab._open_builtin_preset_overlay()
    pop = tab._builtin_preset_popup
    try:
        groups = {h: [k for _l, k in e] for h, e in pop._groups}
        assert sorted(groups[CM]) == sorted(cm)
        assert CM not in pop._more
        assert sorted(k for _l, k in pop._more[I1]) == sorted(set(i1) - shown)
    finally:
        pop.close()


def test_the_rule_is_for_the_paper_only(tab, settings, qapp):
    """Filter OFF: the ticks as they are, ColorMunki's arrow back. And on A4,
    where ColorMunki has ticked presets, its unticked ones stay under the
    arrow."""
    _panel_paper(tab, "A4")
    qapp.processEvents()
    tab._reveal_current_preset_group()
    shown = cp.shown_keys(settings, TC.BUILTIN_PRESET_KEYS)
    cb = tab._preset_combo
    assert set(_on_paper(CM, "A4")) & shown
    assert not cb.view().isRowHidden(tab._preset_arrow_row(CM))
    tab._apply_builtin_presets_shown(shown, paper_filter=False)
    tab._reveal_current_preset_group()
    assert not cb.view().isRowHidden(tab._preset_arrow_row(CM))
