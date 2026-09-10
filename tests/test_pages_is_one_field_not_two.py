""""Pages" exists as two spin boxes and they must never disagree.

An exhaustive sweep of 152 controls, one at a time over four transitions, found
this and named the cause. `TabChart._manual_pages_spin` and
`LayoutOptionsPanel.pages` are two widgets for one number, and they were copied
across only when the user switched between printtarg and the engine
(`_convert_printtarg_to_engine`, `_convert_engine_to_printtarg`) and nowhere
else.

Measured: after a run change, with Generate pressed first so the confirmed rule
says the setting must survive, the panel's box kept 5 while the tab's box went
back to 3, and BOTH leaked the typed value onto the run the user switched to.
One field, two answers, on screen at once.

They are mirrored in both directions now, guarded against the return trip.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication            # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab_with_panel(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("use_chromiq_layout_engine", True)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._refresh_manual_command_preview()
    if getattr(tab, "_manual_layout_panel", None) is None:
        pytest.skip("the layout panel is not built in this configuration")
    if not getattr(tab, "_manual_panel_inited", False):
        tab._init_manual_layout_panel()
    return tab


def test_the_two_pages_boxes_follow_each_other(qapp, tmp_path):
    """MUTATION: remove either `connect` and the matching direction goes red.
    Both were watched."""
    tab = _tab_with_panel(qapp, tmp_path)
    try:
        tabbox = tab._manual_pages_spin
        panelbox = tab._manual_layout_panel.pages
        if tabbox is None or panelbox is None:
            pytest.skip("one of the two Pages boxes is not present")

        tabbox.setValue(5)
        assert int(panelbox.value()) == 5, (
            "the layout panel's Pages did not follow the tab's, so the two "
            "show different numbers for one field")

        panelbox.setValue(3)
        assert int(tabbox.value()) == 3, (
            "the tab's Pages did not follow the layout panel's")
    finally:
        tab.deleteLater()


def test_the_two_boxes_accept_the_same_numbers(qapp, tmp_path):
    """The invariant that keeps the mirror from bouncing.

    Two boxes wired to each other stop only because each returns early when the
    other already holds the value. That breaks down the moment their RANGES
    differ: setting 25 on a box that allows it clamps to 20 on the other, the
    equality never holds, and the two chase each other. `_syncing_pages` is the
    second line of defence, and it is deliberately not what this test proves,
    because removing it changes nothing while the ranges agree. This is the
    thing that must stay true.
    """
    tab = _tab_with_panel(qapp, tmp_path)
    try:
        tabbox = tab._manual_pages_spin
        panelbox = tab._manual_layout_panel.pages
        if tabbox is None or panelbox is None:
            pytest.skip("one of the two Pages boxes is not present")
        assert (tabbox.minimum(), tabbox.maximum()) == \
               (panelbox.minimum(), panelbox.maximum()), (
            f"the two Pages boxes accept different ranges, "
            f"{tabbox.minimum()}-{tabbox.maximum()} against "
            f"{panelbox.minimum()}-{panelbox.maximum()}: one will clamp what "
            "the other sends and they will chase each other")
    finally:
        tab.deleteLater()


def test_the_mirror_settles(qapp, tmp_path):
    """And it really does settle, over a run of changes in both directions."""
    tab = _tab_with_panel(qapp, tmp_path)
    try:
        tabbox = tab._manual_pages_spin
        panelbox = tab._manual_layout_panel.pages
        if tabbox is None or panelbox is None:
            pytest.skip("one of the two Pages boxes is not present")
        for v in (2, 7, 2, 7, 4):
            tabbox.setValue(v)
            assert int(panelbox.value()) == v
        for v in (6, 1, 6, 1, 8):
            panelbox.setValue(v)
            assert int(tabbox.value()) == v
        assert not getattr(tab, "_syncing_pages", False), (
            "the guard was left standing, so a later change would be ignored")
        assert int(tabbox.value()) == int(panelbox.value()) == 8
    finally:
        tab.deleteLater()
