"""B8-1261 (beta 44 challenge F2, inherited from beta 43): "Save as Defaults"
on A3+ Portrait with the layout engine OFF opened the next session on A4 in
Manual, while Guided showed A3+ and the store held ``329x483``.

THE CAUSE. ``_apply_instrument_default_margin`` carries the i1iSis defaults
(A3+ Portrait, ``-n``, ``-P``) and used to undo them on every call for any
other instrument: "not the i1iSis and on A3+ Portrait" was read as the
i1iSis's paper left behind, and set back to A4. ``_restore_defaults`` calls it
AFTER it has set ``-p`` from the store, so a person's own A3+ Portrait was
undone at every start. With the engine on, B8-1228's "put ``-p`` in step with
the saved recipe" came later and hid it; with it off, ``-p`` is the field on
screen. The same undo cleared a saved ``-n`` / ``-P``.

The fix: the i1iSis block acts only when the instrument moves INTO or OUT OF
the i1iSis.

WHY B8-1228'S 54 CELLS MISSED IT: they never saved A3+ Portrait (329x483), the
one paper the undo matches. This file sweeps EVERY paper Manual's Paper field
offers for the ColorMunki (and a Custom one), engine on and off, opening on
Guided and on Manual; and A3+ Portrait for every instrument.

MUTATIONS (red here): the i1iSis block acting on every call again (the beta
44 code): every 329x483 cell with the engine off, and the -P cell.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from ui.tabs import tab_chart as TC                             # noqa: E402

#: Manual's Paper field (printtarg -p), every named entry, in its order
PAPERS = ["A2", "594x420", "329x483", "483x329", "A3", "420x297", "11x17",
          "Legal", "A4", "A4R", "Letter", "LetterR", "203x254", "127x178",
          "4x6"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def store(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


def _session(qapp, s):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    t = TC.TabChart(ArgyllRunner(s), FileManager(s), s)
    qapp.processEvents()
    return t


def _close(qapp, t):
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _choose(t, paper: str, engine: bool) -> None:
    """A person's pick in the Paper field on screen."""
    if engine:
        p = t._manual_layout_panel
        i = p.paper.findData(paper)
        if i < 0:
            w, h = (int(v) for v in paper.split("x"))
            p.custom_w.setValue(w)
            p.custom_h.setValue(h)
            i = p.paper.findData("__custom__")
        p.paper.setCurrentIndex(i)
        return
    pw = t._manual_paper_pw
    i = pw._custom_combo.findData(paper)
    if i < 0:
        w, h = (int(v) for v in paper.split("x"))
        pw._custom_w_spin.setValue(w)
        pw._custom_h_spin.setValue(h)
        i = pw._custom_combo.findData("custom")
    pw._custom_combo.setCurrentIndex(i)


def _round_trip(qapp, s, instr, engine, paper, start):
    s.set("chart_instrument", instr)
    s.set("manual_printtarg_-i_l", instr)
    s.set("use_chromiq_layout_engine", engine)
    s.set("chart_mode", "manual")
    t = _session(qapp, s)
    try:
        assert t._current_mode() == "manual"
        assert (not t._manual_layout_grp.isHidden()) is engine
        _choose(t, paper, engine)
        qapp.processEvents()
        assert t._manual_paper_on_screen() == paper
        t._on_save_defaults()
        s.set("chart_mode", start)       # as closing the window there does
    finally:
        _close(qapp, t)
    t2 = _session(qapp, s)
    return t2


def _check(qapp, t, paper, start, instr):
    """Manual shows the saved paper, whichever module opened, and the store
    still holds it; Guided shows it too when Guided offers it."""
    s = t._settings
    assert t._current_mode() == start
    if start == "guided":
        if t._paper_combo.findData(paper) >= 0:
            assert t._paper_combo.currentData() == paper
        t._manual_btn.click()
        qapp.processEvents()
    assert t._current_mode() == "manual"
    assert t._manual_paper_on_screen() == paper, (
        f"{instr}: Manual opened on {t._manual_paper_on_screen()!r}, "
        f"saved {paper!r}")
    assert t._manual_paper_pw.get_raw_value() == paper
    assert s.get("manual_printtarg_-p_l") == paper
    if t._paper_combo.findData(paper) >= 0:
        t._guided_btn.click()
        qapp.processEvents()
        assert t._paper_combo.currentData() == paper


@pytest.mark.parametrize("start", ["manual", "guided"])
@pytest.mark.parametrize("engine", [True, False], ids=["engine-on",
                                                        "engine-off"])
@pytest.mark.parametrize("paper", PAPERS + ["130x180"])
def test_every_paper_saved_as_default_opens_on_that_paper(
        qapp, store, paper, engine, start):
    t = _round_trip(qapp, store, "CM", engine, paper, start)
    try:
        _check(qapp, t, paper, start, "CM")
    finally:
        _close(qapp, t)


#: (instrument, engine): the CR30 is engine-only, Manual shows the layout
#: panel whatever the setting, so it has no engine-off cell
_INSTR_ENGINE = [(i, e) for i in ("i1", "p3", "SS", "CR30")
                 for e in (True, False) if not (i == "CR30" and not e)]


@pytest.mark.parametrize("start", ["manual", "guided"])
@pytest.mark.parametrize(
    "instr,engine", _INSTR_ENGINE,
    ids=[f"{i}-engine-{'on' if e else 'off'}" for i, e in _INSTR_ENGINE])
def test_a3_plus_portrait_survives_for_every_instrument(
        qapp, store, instr, engine, start):
    t = _round_trip(qapp, store, instr, engine, "329x483", start)
    try:
        _check(qapp, t, "329x483", start, instr)
    finally:
        _close(qapp, t)


def test_a_saved_unlimited_strip_is_not_the_isis_default_undone(qapp, store):
    """The same undo cleared a saved -P on any instrument but the i1iSis."""
    store.set("chart_instrument", "CM")
    store.set("manual_printtarg_-i_l", "CM")
    store.set("use_chromiq_layout_engine", False)
    store.set("chart_mode", "manual")
    t = _session(qapp, store)
    try:
        t._manual_P_pw.set_value(True)
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    t2 = _session(qapp, store)
    try:
        assert bool(t2._manual_P_pw.get_raw_value()) is True
    finally:
        _close(qapp, t2)


def test_the_isis_defaults_still_come_and_go_with_the_isis(qapp, store):
    """What the block is for: choosing the i1iSis moves A4 to A3+ Portrait and
    turns -n and -P on; leaving it undoes that."""
    store.set("chart_instrument", "CM")
    store.set("manual_printtarg_-i_l", "CM")
    store.set("use_chromiq_layout_engine", False)
    store.set("chart_mode", "manual")
    t = _session(qapp, store)
    try:
        t._manual_paper_pw.set_value("A4")
        t._manual_P_pw.set_value(False)
        t._manual_instr_pw.set_value("isis")
        qapp.processEvents()
        assert t._manual_paper_pw.get_raw_value() == "329x483"
        assert bool(t._manual_P_pw.get_raw_value()) is True
        t._manual_instr_pw.set_value("CM")
        qapp.processEvents()
        assert t._manual_paper_pw.get_raw_value() == "A4"
        assert bool(t._manual_P_pw.get_raw_value()) is False
        # …and a later call with the instrument unchanged leaves a person's
        # A3+ Portrait alone.
        t._manual_paper_pw.set_value("329x483")
        t._apply_instrument_default_margin()
        assert t._manual_paper_pw.get_raw_value() == "329x483"
    finally:
        _close(qapp, t)
