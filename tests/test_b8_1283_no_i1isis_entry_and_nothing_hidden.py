"""B8-1283, as the owner's ruling of 2026-11-14 changed it.

Knut answered B8-1283 on 2026-09-26 (#182 5845519118): *"No i1iSis entry. Do
not hide."* This file pinned that: the old printtarg entry "i1iSis (via
i1Profiler)" had no layout-engine entry, and choosing it did not hide the
layout panel.

The owner's newer ruling (Basti, 2026-11-14, recorded under §2y/§2z of
`docs/design/issue_182_answers.md`, Knut's text kept): *"the isis entry
without the beta option enabled is removed. and with the new option in beta
the users get the new improved isis/xl entry"*. The entry was removed by the
owner's ruling of 2026-11-14, so this file now pins the new state:

* the old code ``isis`` is offered nowhere, with the Beta off or on;
* with the Beta "X-Rite i1iSis charts" off, no i1iSis entry anywhere;
* with it on, the layout engine, the layout panel, Guided and Manual HAVE
  the new entry ``XRISIS``, and choosing it does not hide the panel (the
  second half of Knut's ruling, "Do not hide", still holds).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(qapp, tmp_path, on: bool):
    from workflow.isis import support
    support.set_enabled_for_this_process(on)
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs import tab_chart as TC
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / f"s{on}.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("use_chromiq_layout_engine", True)
    t = TC.TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    qapp.processEvents()
    return t


@pytest.fixture(autouse=True)
def _reset_switch():
    yield
    from workflow.isis import support
    support.set_enabled_for_this_process(None)


def _close(qapp, t):
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _codes(combo):
    return [combo.itemData(i) for i in range(combo.count())]


@pytest.mark.parametrize("on", [False, True])
def test_the_old_isis_entry_is_offered_nowhere(qapp, tmp_path, on):
    t = _tab(qapp, tmp_path, on)
    try:
        assert "isis" not in _codes(t._manual_layout_panel.instr)
        assert "isis" not in _codes(t._instr_combo)
        params = t._load_yaml_params()
        i = next(p for p in params["printtarg"] if p["flag"] == "-i")
        assert "isis" not in i["choices"]
        assert "i1iSis (via i1Profiler)" not in i["tooltip_body"]
    finally:
        _close(qapp, t)


def test_with_the_beta_off_there_is_no_i1isis_entry(qapp, tmp_path):
    t = _tab(qapp, tmp_path, False)
    try:
        assert "XRISIS" not in _codes(t._manual_layout_panel.instr)
        assert "XRISIS" not in _codes(t._instr_combo)
        i = next(p for p in t._load_yaml_params()["printtarg"]
                 if p["flag"] == "-i")
        assert "XRISIS" not in i["choices"]
    finally:
        _close(qapp, t)
    from workflow.layout_engine import instruments
    with pytest.raises(ValueError):
        instruments.build("XRISIS")


def test_with_the_beta_on_the_engine_has_the_i1isis_entry(qapp, tmp_path):
    t = _tab(qapp, tmp_path, True)
    try:
        assert "XRISIS" in _codes(t._manual_layout_panel.instr)
        assert "XRISIS" in _codes(t._instr_combo)
        i = next(p for p in t._load_yaml_params()["printtarg"]
                 if p["flag"] == "-i")
        assert "XRISIS" in i["choices"]
        # "Do not hide": choosing it leaves the layout panel on screen
        t._manual_instr_pw.set_value("XRISIS")
        t._refresh_manual_command_preview()
        qapp.processEvents()
        assert t._manual_get("printtarg", "-i", "") == "XRISIS"
        assert not t._manual_layout_grp.isHidden()
    finally:
        _close(qapp, t)
    from workflow.layout_engine import instruments
    assert instruments.build("XRISIS").key == "XRISIS"
