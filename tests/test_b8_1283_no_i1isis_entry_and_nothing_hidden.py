"""B8-1283, answered by Knut (#182 5845519118, 2026-09-26), no change:

*"No i1iSis entry. Do not hide. That setting is only used if a user measures a
chart outside ChromIQ (in i1Profiler) and then imports the results back into
ChromIQ for creating the report."*

The question was whether, with the ChromIQ layout engine on, choosing the
i1iSis should hide the layout panel (and show printtarg's fields, as with the
engine off) or whether the engine should get an i1iSis entry. Neither: this
pins the app as it is, so a later change cannot do either without the ruling
being revisited.

MUTATIONS (mutations.txt of the k50 proof): the i1iSis added to the layout
panel's instrument list, red; the panel hidden for the i1iSis with the engine
on (the frame's predicate answering False for it), red.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from ui.tabs import tab_chart as TC                             # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def tab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("use_chromiq_layout_engine", True)
    t = TC.TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    qapp.processEvents()
    yield t
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def test_the_layout_panel_has_no_i1isis_entry(tab):
    instr = tab._manual_layout_panel.instr
    codes = [instr.itemData(i) for i in range(instr.count())]
    assert "isis" not in codes, "Knut: 'No i1iSis entry.'"


def test_the_i1isis_does_not_hide_the_layout_panel(tab, qapp):
    """With the engine on, printtarg's -i on the i1iSis leaves the layout
    panel on screen and printtarg's fields hidden."""
    tab._manual_instr_pw.set_value("isis")
    tab._refresh_manual_command_preview()
    qapp.processEvents()
    assert tab._manual_get("printtarg", "-i", "") == "isis"
    assert not tab._manual_layout_grp.isHidden(), "Knut: 'Do not hide.'"
    assert tab._manual_printtarg_grp.isHidden()
