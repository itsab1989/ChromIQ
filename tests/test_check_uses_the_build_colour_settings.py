"""Check & Refine checks a profile with the colour settings it was built with
(issue 217, 2026-11-21; UMM §11, "the check uses the colour settings the
profile was built with", awaiting confirmation).

A tester built with the CIE 2015 2° observer; "Analyse Profile Quality" ran
profcheck with its own 1931 2° and reported 1.63 / 6.14 instead of 0.34 /
2.4, and Guided Refinement sent him to re-read good strips. These tests hold:

* every build records observer / illuminant / FWA (`profile_build.colorimetry`);
* Guided and Manual pass the profile's own to profcheck when asked, warn on a
  mismatch, and each button does what it says;
* a profile built with the defaults, a profile that records nothing, and a
  measurement without spectra are checked with EXACTLY the old arguments;
* a check run with other settings says so in the result window and report;
* the app log names the settings of every check and the source of every
  change of the colour controls.

profcheck itself never runs here: the runner is replaced and its argument
list is asserted (`ProfcheckRunner._build_args`).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import check_colorimetry as cc  # noqa: E402

STEM = "Obs-Check"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_SPECTRAL_TI3 = """CTI3

DESCRIPTOR "Argyll Calibration Target chart information 3"
ORIGINATOR "Argyll chartread"
COLOR_REP "RGB_XYZ"
SPECTRAL_BANDS "36"
SPECTRAL_START_NM "380.000000"
SPECTRAL_END_NM "730.000000"
NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y
END_DATA_FORMAT
NUMBER_OF_SETS 1
BEGIN_DATA
1 A1 100 100 100 90.0 93.0
END_DATA
"""

_PLAIN_TI3 = _SPECTRAL_TI3.replace('SPECTRAL_BANDS "36"\n', "").replace(
    'SPECTRAL_START_NM "380.000000"\n', "").replace(
    'SPECTRAL_END_NM "730.000000"\n', "")


def _settings(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    s.set("custom_output_path", str(work))
    return s, work


def _run(work, *, spectral=True):
    from core.file_manager import Project
    proj = Project.create(work / STEM, STEM)
    run = proj.current_run()
    ti3 = run.dir / f"{STEM}.ti3"
    ti3.write_text(_SPECTRAL_TI3 if spectral else _PLAIN_TI3,
                   encoding="utf-8")
    icc = run.dir / f"{STEM}.icc"
    icc.write_bytes(b"not a real profile" * 10)
    return run, ti3, icc


def _record(run, icc, *, at=None, **colour):
    """The record a build writes (`TabProfile._record_profile_build`)."""
    from workflow.profile_builder import ProfileParams
    info = {"builder": "colprof", "profile": Path(icc).name,
            "at": (at or datetime.now()).isoformat(timespec="seconds")}
    info.update(cc.record_for_build(ProfileParams(
        ti3_path=run.dir / f"{STEM}.ti3", **colour)))
    run.record_profile_build(info)


def _check_tab(s, ti3, icc, mode="guided"):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_check_refine import TabCheckRefine
    tab = TabCheckRefine(ArgyllRunner(s), s)
    tab.set_paths(ti3, icc, propagate=False)
    tab._switch_mode(mode)
    return tab


def _capture(monkeypatch, tab, answer=None):
    """Replace profcheck and the question; returns (runs, asked)."""
    runs, asked = [], []

    def _run(params, on_line, on_finish):
        runs.append((params, tab._checker._build_args(params)))

    monkeypatch.setattr(tab._checker, "run", _run)

    def _ask(built, check):
        asked.append((built, check))
        return answer if answer is not None else "cancel"

    monkeypatch.setattr(tab, "_ask_colorimetry", _ask)
    return runs, asked


def _obs(tab, mode):
    return (tab._obs_combo if mode == "guided" else tab._m_obs_combo)


# ---------------------------------------------------------------------------
# what a build records
# ---------------------------------------------------------------------------

def test_a_build_records_what_it_passed_on():
    from workflow.profile_builder import ProfileParams
    p = ProfileParams(ti3_path=Path("x.ti3"), observer="2015_2",
                      illuminant="D65", fwa_enabled=True, fwa_illum="")
    assert cc.record_for_build(p) == {"colorimetry": {
        "observer": "2015_2", "illuminant": "D65", "fwa": True,
        "fwa_illum": "D50"}}
    # the defaults are written out as ArgyllCMS's defaults
    assert cc.record_for_build(ProfileParams(ti3_path=Path("x.ti3"))) == {
        "colorimetry": {"observer": "1931_2", "illuminant": "D50",
                        "fwa": False, "fwa_illum": ""}}


def test_the_extra_arguments_win_as_they_do_on_the_command_line():
    from workflow.profile_builder import ProfileParams
    p = ProfileParams(ti3_path=Path("x.ti3"), observer="",
                      extra_args="-o 2015_10 -iD65")
    c = cc.from_profile_params(p)
    assert (c.normalised().observer, c.normalised().illuminant) == (
        "2015_10", "D65")


def test_the_build_profile_tab_writes_the_record(tmp_path, qtbot):
    """Guided's observer combo, through `_collect_params`, reaches the
    run's meta.json (`_record_profile_build`)."""
    from tests.test_the_new_profile_engine_is_one_switch import (
        _run_with_ti3, _tab)
    tab = _tab(tmp_path, profile_engine_beta=False)
    qtbot.addWidget(tab)
    run, ti3 = _run_with_ti3(tab, tmp_path)
    tab._obs_combo.setCurrentIndex(tab._obs_combo.findData("2015_2"))
    tab._active_params = tab._collect_params("guided")
    tab._note_a_colprof_build(ti3.with_suffix(".icc"))
    rec = run.load_meta().profile_build
    assert rec["colorimetry"]["observer"] == "2015_2"
    assert rec["profile"] == ti3.with_suffix(".icc").name


# ---------------------------------------------------------------------------
# reading it back
# ---------------------------------------------------------------------------

def test_the_record_is_read_only_for_the_file_it_names(tmp_path):
    _s, work = _settings(tmp_path)
    run, _ti3, icc = _run(work)
    assert not cc.built_colorimetry(icc).known          # nothing recorded
    _record(run, icc, observer="2015_2")
    got = cc.built_colorimetry(icc)
    assert got.known and got.colorimetry.observer == "2015_2"
    other = run.dir / "merged.icc"
    other.write_bytes(b"x")
    assert not cc.built_colorimetry(other).known
    # a profile replaced after its record was written is not described by it
    _record(run, icc, at=datetime.now() - timedelta(hours=2),
            observer="2015_2")
    assert not cc.built_colorimetry(icc).known
    # a record from before this change has no colour settings
    run.record_profile_build({"builder": "colprof", "profile": icc.name,
                              "at": datetime.now().isoformat()})
    assert not cc.built_colorimetry(icc).known
    assert "before ChromIQ recorded" in cc.built_colorimetry(icc).why


def test_spectral_readings_are_told_from_the_header(tmp_path):
    _s, work = _settings(tmp_path)
    _run_, ti3, _icc = _run(work)
    assert cc.has_spectral(ti3)
    plain = tmp_path / "plain.ti3"
    plain.write_text(_PLAIN_TI3, encoding="utf-8")
    assert not cc.has_spectral(plain)


# ---------------------------------------------------------------------------
# Analyse Profile Quality, Guided and Manual
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", ["guided", "manual"])
def test_the_profiles_settings_are_used_when_chosen(qapp, tmp_path,
                                                    monkeypatch, mode):
    s, work = _settings(tmp_path)
    run, ti3, icc = _run(work)
    _record(run, icc, observer="2015_2")
    tab = _check_tab(s, ti3, icc, mode)
    runs, asked = _capture(monkeypatch, tab, answer="profile")
    assert _obs(tab, mode).currentData() == "1931_2"
    tab._on_run()
    assert len(asked) == 1
    params, args = runs[0]
    assert params.observer == "2015_2"
    assert args[args.index("-o") + 1] == "2015_2"
    # the controls of the mode that ran now show what the check used...
    assert _obs(tab, mode).currentData() == "2015_2"
    # ...the other mode's are left alone, and nothing is saved as default
    other = "manual" if mode == "guided" else "guided"
    assert _obs(tab, other).currentData() == "1931_2"
    key = ("profcheck_observer" if mode == "guided"
           else "manual2_profcheck_observer")
    assert s.get(key, "1931_2") == "1931_2"
    assert tab._colour_insisted is None
    assert "the colour settings the profile was built with" in \
        tab._log.toPlainText()
    # the second check matches and asks nothing
    tab._on_run()
    assert len(asked) == 1 and runs[1][0].observer == "2015_2"


@pytest.mark.parametrize("mode", ["guided", "manual"])
def test_check_with_my_settings_keeps_them_and_says_so(qapp, tmp_path,
                                                       monkeypatch, mode):
    s, work = _settings(tmp_path)
    run, ti3, icc = _run(work)
    _record(run, icc, observer="2015_2")
    tab = _check_tab(s, ti3, icc, mode)
    runs, asked = _capture(monkeypatch, tab, answer="mine")
    tab._on_run()
    params, args = runs[0]
    assert "-o" not in args and params.observer == "1931_2"
    assert tab._colour_insisted is not None
    note = tab._colour_insisted_text()
    assert note.startswith(
        "Checked with other colour settings than the profile was built with")
    assert "CIE 2015 2°" in note and "CIE 1931 2°" in note
    # the saved report says it, under the numbers
    from ui.tabs.tab_check_refine import TabCheckRefine
    from workflow.profcheck_runner import ProfcheckResult
    from workflow.refine_plan import build_plan
    text = TabCheckRefine._report_summary_text(
        ProfcheckResult(avg_de=1.6, peak_de=6.1),
        build_plan([], 2.0, "ΔE00", None), colour_note=note)
    assert note in text
    assert _obs(tab, mode).currentData() == "1931_2"


def test_cancel_runs_nothing(qapp, tmp_path, monkeypatch):
    s, work = _settings(tmp_path)
    run, ti3, icc = _run(work)
    _record(run, icc, observer="2015_2")
    tab = _check_tab(s, ti3, icc)
    runs, asked = _capture(monkeypatch, tab, answer="cancel")
    tab._on_run()
    assert asked and not runs
    assert tab._obs_combo.currentData() == "1931_2"


def test_a_matching_tab_is_not_asked(qapp, tmp_path, monkeypatch):
    s, work = _settings(tmp_path)
    run, ti3, icc = _run(work)
    _record(run, icc, observer="2015_2", illuminant="D65")
    tab = _check_tab(s, ti3, icc, "manual")
    tab._m_obs_combo.setCurrentIndex(tab._m_obs_combo.findData("2015_2"))
    tab._m_illum_combo.setCurrentIndex(tab._m_illum_combo.findData("D65"))
    runs, asked = _capture(monkeypatch, tab)
    tab._on_run()
    assert not asked
    args = runs[0][1]
    assert args[args.index("-o") + 1] == "2015_2"
    assert args[args.index("-i") + 1] == "D65"


def _plain_args(s, ti3, icc, monkeypatch, mode):
    """The arguments the check passes with no record anywhere."""
    tab = _check_tab(s, ti3, icc, mode)
    runs, asked = _capture(monkeypatch, tab)
    tab._on_run()
    assert not asked
    return runs[0][1], tab


@pytest.mark.parametrize("mode", ["guided", "manual"])
def test_the_common_case_is_exactly_as_before(qapp, tmp_path, monkeypatch,
                                              mode):
    """A profile built with the defaults: the same arguments as a profile
    that records nothing, which are the arguments of 4.3.54."""
    s, work = _settings(tmp_path)
    run, ti3, icc = _run(work)
    before, tab0 = _plain_args(s, ti3, icc, monkeypatch, mode)
    assert before == tab0._checker._build_args(tab0._collect_params())
    _record(run, icc)                         # built with the defaults
    after, tab = _plain_args(s, ti3, icc, monkeypatch, mode)
    assert after == before
    assert "-o" not in after and "-i" not in after
    assert "ChromIQ does not know" not in tab._log.toPlainText()


def test_unknown_build_settings_keep_todays_check_and_say_so(
        qapp, tmp_path, monkeypatch):
    s, work = _settings(tmp_path)
    _run_, ti3, icc = _run(work)
    args, tab = _plain_args(s, ti3, icc, monkeypatch, "guided")
    assert "-o" not in args
    assert "ChromIQ does not know which colour settings" in \
        tab._log.toPlainText()
    assert tab._colour_insisted is None


def test_without_spectra_nothing_is_asked(qapp, tmp_path, monkeypatch):
    s, work = _settings(tmp_path)
    run, ti3, icc = _run(work, spectral=False)
    _record(run, icc, observer="2015_2")
    tab = _check_tab(s, ti3, icc)
    runs, asked = _capture(monkeypatch, tab)
    tab._on_run()
    assert not asked and "-o" not in runs[0][1]


# ---------------------------------------------------------------------------
# the window
# ---------------------------------------------------------------------------

def test_the_window_offers_three_buttons_side_by_side(qapp, tmp_path):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QDialogButtonBox
    s, work = _settings(tmp_path)
    _run_, ti3, icc = _run(work)
    tab = _check_tab(s, ti3, icc)
    dlg, buttons = tab._colorimetry_box(cc.Colorimetry("2015_2"),
                                        cc.Colorimetry("1931_2"))
    assert set(buttons) == {"profile", "mine", "cancel"}
    assert dlg.defaultButton() is buttons["profile"]
    assert dlg.escapeButton() is buttons["cancel"]
    assert buttons["profile"].text() == "Use the profile's settings"
    assert buttons["mine"].text() == "Check with my settings"
    box = dlg.findChild(QDialogButtonBox)
    assert box.orientation() == Qt.Orientation.Horizontal
    assert "CIE 2015 2°" in dlg.informativeText()
    assert "CIE 1931 2°" in dlg.informativeText()
    assert "—" not in dlg.informativeText() + dlg.text()
    dlg.deleteLater()


@pytest.mark.parametrize("key", ["profile", "mine", "cancel"])
def test_each_button_answers_for_itself(qapp, tmp_path, monkeypatch, key):
    from PyQt6.QtWidgets import QMessageBox
    s, work = _settings(tmp_path)
    _run_, ti3, icc = _run(work)
    tab = _check_tab(s, ti3, icc)
    real_box = tab._colorimetry_box
    holder = {}

    def _box(b, c):
        dlg, buttons = real_box(b, c)
        holder["b"] = buttons
        return dlg, buttons

    monkeypatch.setattr(tab, "_colorimetry_box", _box)
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: holder["b"][key].click() or 0)
    assert tab._ask_colorimetry(cc.Colorimetry("2015_2"),
                                cc.Colorimetry()) == key


def test_the_result_window_carries_the_note(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QDialog, QLabel
    from workflow.profcheck_runner import ProfcheckResult
    from workflow.refine_plan import build_plan
    s, work = _settings(tmp_path)
    _run_, ti3, icc = _run(work)
    tab = _check_tab(s, ti3, icc)
    tab._colour_insisted = {"built": cc.Colorimetry("2015_2"),
                            "check": cc.Colorimetry()}
    seen = {}

    def _exec(dlg):
        seen["note"] = dlg.findChild(QLabel, "cr_colour_settings_note")
        seen["text"] = seen["note"].text() if seen["note"] else ""
        return 0

    monkeypatch.setattr(QDialog, "exec", _exec)
    tab._show_result_dialog(ProfcheckResult(avg_de=1.6, peak_de=6.1),
                            build_plan([], 2.0, "ΔE00", None), None)
    assert seen["note"] is not None
    assert "Checked with other colour settings" in seen["text"]
    tab._colour_insisted = None
    tab._show_result_dialog(ProfcheckResult(avg_de=0.3, peak_de=2.4),
                            build_plan([], 2.0, "ΔE00", None), None)
    assert seen["note"] is None


# ---------------------------------------------------------------------------
# the log
# ---------------------------------------------------------------------------

def test_every_check_logs_its_settings_and_the_choice(qapp, tmp_path,
                                                      monkeypatch, caplog):
    s, work = _settings(tmp_path)
    run, ti3, icc = _run(work)
    _record(run, icc, observer="2015_2")
    tab = _check_tab(s, ti3, icc)
    _capture(monkeypatch, tab, answer="mine")
    with caplog.at_level(logging.INFO):
        tab._on_run()
    line = [r.getMessage() for r in caplog.records
            if r.getMessage().startswith("Check colour settings:")][-1]
    assert "profile built with: observer 2015_2" in line
    assert "check uses: observer 1931_2" in line
    assert "warning shown, chosen: Check with my settings" in line
    assert tab._colour_record == line
    assert "tab set to" not in line          # the tab's own settings were used


def test_the_log_names_the_tabs_setting_when_the_profiles_was_used(
        qapp, tmp_path, monkeypatch, caplog):
    s, work = _settings(tmp_path)
    run, ti3, icc = _run(work)
    _record(run, icc, observer="2015_2")
    tab = _check_tab(s, ti3, icc)
    _capture(monkeypatch, tab, answer="profile")
    with caplog.at_level(logging.INFO):
        tab._on_run()
    line = tab._colour_record
    assert "tab set to: observer 1931_2" in line
    assert "check uses: observer 2015_2" in line
    assert "chosen: Use the profile's settings" in line


def test_an_unknown_profile_is_logged_as_unknown(qapp, tmp_path,
                                                 monkeypatch, caplog):
    s, work = _settings(tmp_path)
    _run_, ti3, icc = _run(work)
    tab = _check_tab(s, ti3, icc)
    _capture(monkeypatch, tab)
    with caplog.at_level(logging.INFO):
        tab._on_run()
    assert any("profile built with: unknown (the run records no profile "
               "build)" in r.getMessage() for r in caplog.records)


def _changes(caplog):
    return [r.getMessage() for r in caplog.records
            if r.getMessage().startswith("Setting changed:")]


def test_the_warning_is_named_as_the_source_of_its_change(
        qapp, tmp_path, monkeypatch, caplog):
    s, work = _settings(tmp_path)
    run, ti3, icc = _run(work)
    _record(run, icc, observer="2015_2")
    tab = _check_tab(s, ti3, icc)
    _capture(monkeypatch, tab, answer="profile")
    with caplog.at_level(logging.INFO):
        tab._on_run()
    got = _changes(caplog)
    assert any("Check & Refine, Guided, observer: '1931_2' -> '2015_2' "
               "(source: the warning window" in m for m in got), got


def test_build_profile_names_every_source(tmp_path, qtbot, caplog):
    from PyQt6.QtWidgets import QApplication
    from tests.test_the_new_profile_engine_is_one_switch import _tab
    tab = _tab(tmp_path, profile_engine_beta=False)
    qtbot.addWidget(tab)
    combo = tab._m_obs_combo
    with caplog.at_level(logging.INFO):
        # a saved Manual preset
        tab._m_load_presets = lambda: {"P": {"observer": "2015_2"}}
        tab._m_populate_preset_combo({"P": {}})
        tab._m_preset_combo.setCurrentIndex(1)
        # the person, in the control
        i = combo.findData("1964_10")
        combo.setCurrentIndex(i)
        combo.activated.emit(i)
        # a path that names no source
        combo.setCurrentIndex(combo.findData(""))
        QApplication.processEvents()
    got = _changes(caplog)
    assert any("Build Profile, Manual, observer: '' -> '2015_2' (source: "
               "the Manual preset 'P')" in m for m in got), got
    assert any("'2015_2' -> '1964_10' (source: the user, in the control)"
               in m for m in got), got
    assert any("'1964_10' -> '' (source: set by the program, no source "
               "named)" in m for m in got), got


def test_the_targets_stored_settings_are_named(tmp_path, qtbot, caplog,
                                               monkeypatch):
    from tests.test_the_new_profile_engine_is_one_switch import (
        _run_with_ti3, _tab)
    from workflow import per_target_settings as pts
    tab = _tab(tmp_path, profile_engine_beta=False)
    qtbot.addWidget(tab)
    run, _ti3 = _run_with_ti3(tab, tmp_path)
    meta = run.load_meta()
    meta.profile_settings = {"observer": "2015_2", "g_observer": "2015_10"}
    run.save_meta(meta)

    monkeypatch.setattr(pts, "store_for_target", lambda _ctl: run)
    with caplog.at_level(logging.INFO):
        tab.load_target_settings()
    got = _changes(caplog)
    assert any("Manual, observer: '' -> '2015_2' (source: the target's "
               "stored settings (run1))" in m for m in got), got
    assert any("Guided, observer:" in m and "'2015_10'" in m
               and "(source: the target's stored settings (run1), Guided)"
               in m for m in got), got


# ---------------------------------------------------------------------------
# the tools without colour controls
# ---------------------------------------------------------------------------

def test_verify_profile_follows_the_record(tmp_path):
    from workflow.profcheck_runner import ProfcheckParams
    _s, work = _settings(tmp_path)
    run, ti3, icc = _run(work)
    p = ProfcheckParams(ti3_path=ti3, icc_path=icc)
    same, note = cc.follow_profile(p, "Verify profile")
    assert same == p and note == ""                    # nothing recorded
    _record(run, icc, observer="2015_2")
    got, note = cc.follow_profile(p, "Verify profile")
    assert got.observer == "2015_2" and "CIE 2015 2°" in note
    _record(run, icc)                                    # the defaults
    got, note = cc.follow_profile(p, "Verify profile")
    assert got == p and note == ""


def test_the_tools_call_it():
    import inspect

    from ui.dialogs import ti3_info_dialog, tools_dialogs
    assert 'follow_profile(params, "Verify profile")' in inspect.getsource(
        tools_dialogs)
    assert 'follow_profile(params, "Inspect a measurement")' in \
        inspect.getsource(ti3_info_dialog)
