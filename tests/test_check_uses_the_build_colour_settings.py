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
import time
from datetime import datetime
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
    info.update(cc.fingerprint(icc))
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
    """Review B1: a plain -f ("Same as illuminant (-i)") simulates the -i
    illuminant, as colprof 3.5.0 computes it (measured: "-i D65 -f" fits
    like "-i D65 -fD65", not like "-i D65 -fD50")."""
    from workflow.profile_builder import ProfileParams
    p = ProfileParams(ti3_path=Path("x.ti3"), observer="2015_2",
                      illuminant="D65", fwa_enabled=True, fwa_illum="")
    assert cc.record_for_build(p) == {"colorimetry": {
        "observer": "2015_2", "illuminant": "D65", "fwa": True,
        "fwa_illum": "D65"}}
    a = ProfileParams(ti3_path=Path("x.ti3"), illuminant="A",
                      fwa_enabled=True, fwa_illum="")
    assert cc.record_for_build(a)["colorimetry"]["fwa_illum"] == "A"
    # ...and the check gets that illuminant by name, which profcheck reads
    # exactly like the build's plain -f
    from workflow.profcheck_runner import ProfcheckParams, ProfcheckRunner
    built = cc.Colorimetry.from_record(cc.record_for_build(p)["colorimetry"])
    args = ProfcheckRunner(None)._build_args(cc.apply_to_check(
        ProfcheckParams(ti3_path=Path("x.ti3"), icc_path=Path("x.icc")),
        built))
    assert "-fD65" in args and args[args.index("-i") + 1] == "D65"
    assert "-fD50" not in args
    # the tab set correctly (D65, FWA on, D65) is NOT a mismatch
    assert cc.differences(built, cc.Colorimetry("2015_2", "D65", True,
                                                "D65")) == []
    assert cc.describe(built).endswith("FWA compensation on, simulating D65")
    # the defaults are written out as ArgyllCMS's defaults
    assert cc.record_for_build(ProfileParams(ti3_path=Path("x.ti3"))) == {
        "colorimetry": {"observer": "1931_2", "illuminant": "D50",
                        "fwa": False, "fwa_illum": ""}}


@pytest.mark.parametrize("extra,want", [
    # each measured with colprof 3.5.0 on the spectral test file
    ("-f D65", ("1931_2", "D50", True, "D65")),        # == -fD65
    ("-fD65", ("1931_2", "D50", True, "D65")),
    ("-fD65 -f", ("1931_2", "D50", True, "D65")),      # == -fD65
    ("-i A -f", ("1931_2", "A", True, "A")),
    ("-i A -f -i D65", ("1931_2", "D65", True, "D65")),  # == -i D65 -f
    ("-o 1964_10 -o 2015_2", ("2015_2", "D50", False, "")),  # last wins
    ("-i D65 -iA", ("1931_2", "A", False, "")),
])
def test_every_form_of_the_extra_arguments(extra, want):
    from workflow.profile_builder import ProfileParams
    c = cc.from_profile_params(ProfileParams(ti3_path=Path("x.ti3"),
                                             extra_args=extra)).normalised()
    assert (c.observer, c.illuminant, c.fwa, c.fwa_illum) == want


def test_a_spectral_file_is_named_never_with_its_path():
    """Review m4: a .sp illuminant typed in the extra arguments is recorded
    and logged by its file name only, and a check cannot reproduce it, so
    the profile counts as one whose settings the check cannot use."""
    from workflow.profile_builder import ProfileParams
    p = ProfileParams(ti3_path=Path("x.ti3"),
                      extra_args="-i /Users/someone/lights/my-lamp.sp")
    rec = cc.record_for_build(p)["colorimetry"]
    assert rec["illuminant"] == "my-lamp.sp" and rec["files"] == ["my-lamp.sp"]
    assert "/Users" not in repr(rec)
    c = cc.from_profile_params(p)
    assert "/Users" not in c.for_log() and "/Users" not in cc.describe(c)


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
    icc.write_bytes(b"another profile" * 10)
    gone = cc.built_colorimetry(icc)
    assert not gone.known and gone.reason == cc.UNKNOWN_CHANGED
    # a record from before this change has no colour settings
    run.record_profile_build({"builder": "colprof", "profile": icc.name,
                              "at": datetime.now().isoformat()})
    assert not cc.built_colorimetry(icc).known
    assert "before ChromIQ recorded" in cc.built_colorimetry(icc).why
    assert cc.built_colorimetry(icc).reason == cc.UNKNOWN_OLD


def test_an_older_file_put_back_is_not_the_recorded_one(tmp_path):
    """Review M1: a profile restored from old/ (its older date kept) after a
    rebuild with other settings is not described by the new record."""
    import os
    _s, work = _settings(tmp_path)
    run, _ti3, icc = _run(work)
    old_bytes = b"the first build" * 20
    icc.write_bytes(old_bytes)
    _record(run, icc, observer="1964_10")
    icc.write_bytes(b"the second build" * 20)          # rebuilt, 2015 2°
    _record(run, icc, observer="2015_2")
    assert cc.built_colorimetry(icc).colorimetry.observer == "2015_2"
    icc.write_bytes(old_bytes)                          # put back by hand
    past = time.time() - 3600
    os.utime(icc, (past, past))                         # with its old date
    got = cc.built_colorimetry(icc)
    assert not got.known and got.reason == cc.UNKNOWN_CHANGED


def test_a_replacement_within_two_minutes_is_not_the_recorded_one(tmp_path):
    """Review M1: no time window. A file replaced seconds after its record
    (a quick -qf build elsewhere, a copy) is unknown."""
    _s, work = _settings(tmp_path)
    run, _ti3, icc = _run(work)
    _record(run, icc, observer="2015_2")
    icc.write_bytes(b"replaced at once" * 10)
    assert not cc.built_colorimetry(icc).known


def test_a_calibrated_copy_keeps_its_sources_settings(tmp_path):
    """Review m1: calibrated.icc is made by applycal from a recorded
    profile and keeps its colour settings (`record_derived`); a later build
    drops the derived record."""
    _s, work = _settings(tmp_path)
    run, _ti3, icc = _run(work)
    _record(run, icc, observer="2015_2")
    cal = run.dir / "calibrated.icc"
    cal.write_bytes(b"calibrated copy" * 10)
    assert cc.built_colorimetry(cal).reason == cc.UNKNOWN_OTHER_FILE
    src = cc.built_colorimetry(icc)
    assert cc.record_derived(cal, src.colorimetry, source=icc.name)
    got = cc.built_colorimetry(cal)
    assert got.known and got.colorimetry.observer == "2015_2"
    assert cc.built_colorimetry(icc).known            # the main record stays
    _record(run, icc, observer="1964_10")             # rebuilt
    assert not cc.built_colorimetry(cal).known


def test_apply_calibration_records_the_copy(tmp_path, qtbot):
    """The Build Profile tab's Apply Calibration success path calls
    `record_derived` with the source's settings."""
    import inspect

    from ui.tabs.tab_profile import TabProfile
    src = inspect.getsource(TabProfile._on_applycal_run)
    assert "record_derived(result, src.colorimetry" in src
    assert "record_derived(kept, from_profile_params(cparams)" in \
        inspect.getsource(TabProfile._on_comparison_done)


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
    assert "ChromIQ has no record" not in tab._log.toPlainText()


def test_unknown_build_settings_keep_todays_check_and_say_so(
        qapp, tmp_path, monkeypatch):
    s, work = _settings(tmp_path)
    _run_, ti3, icc = _run(work)
    args, tab = _plain_args(s, ti3, icc, monkeypatch, "guided")
    assert "-o" not in args
    assert "ChromIQ has no record of the colour settings" in \
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


# ---------------------------------------------------------------------------
# fix round (review of 2026-11-21): m1 to m5
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case,expect", [
    ("old", "built before ChromIQ recorded the colour settings"),
    ("other", "is about its last build (Obs-Check.icc)"),
    ("changed", "not the one its build recorded"),
    ("none", "ChromIQ has no record of the colour settings"),
])
def test_the_unknown_note_says_why(qapp, tmp_path, monkeypatch, case, expect):
    s, work = _settings(tmp_path)
    run, ti3, icc = _run(work)
    target = icc
    if case == "old":
        run.record_profile_build({"builder": "colprof", "profile": icc.name})
    elif case == "other":
        _record(run, icc, observer="2015_2")
        target = run.dir / "calibrated.icc"
        target.write_bytes(b"made elsewhere" * 5)
    elif case == "changed":
        _record(run, icc, observer="2015_2")
        icc.write_bytes(b"replaced" * 9)
    tab = _check_tab(s, ti3, target)
    runs, asked = _capture(monkeypatch, tab)
    tab._on_run()
    text = tab._log.toPlainText()
    assert not asked and expect in text, text
    assert text.count("The check uses the settings on this tab") == 1
    assert "earlier version" not in text or case == "none"


def test_the_fwa_gate_is_named_and_logged_as_it_runs(qapp, tmp_path,
                                                     monkeypatch, caplog):
    """Review m3: the synthetic measurement names no instrument, so the FWA
    gate leaves -f out; the note and the log say what profcheck gets."""
    from workflow.profile_builder import ProfileParams
    s, work = _settings(tmp_path)
    run, ti3, icc = _run(work)
    # built (with -f) from a measurement the gate lets through; checked
    # against one it refuses -f for
    info = {"builder": "colprof", "profile": icc.name}
    info.update(cc.record_for_build(ProfileParams(
        ti3_path=Path("elsewhere.ti3"), illuminant="D65", fwa_enabled=True)))
    info.update(cc.fingerprint(icc))
    run.record_profile_build(info)
    assert info["colorimetry"]["fwa"] is True
    tab = _check_tab(s, ti3, icc)
    runs, asked = _capture(monkeypatch, tab, answer="profile")
    with caplog.at_level(logging.INFO):
        tab._on_run()
    assert asked
    assert "FWA compensation is left out" in tab._log.toPlainText()
    assert "check uses: observer 1931_2, illuminant D65, FWA compensation " \
        "off" in tab._colour_record


def test_a_value_the_controls_cannot_show_is_named(qapp, tmp_path,
                                                   monkeypatch):
    """Review m4: an FWA illuminant the tab's list has no entry for."""
    from workflow.profile_builder import ProfileParams
    s, work = _settings(tmp_path)
    run, ti3, icc = _run(work)
    info = {"builder": "colprof", "profile": icc.name}
    info.update(cc.record_for_build(ProfileParams(
        ti3_path=Path("elsewhere.ti3"), extra_args="-fM1")))
    info.update(cc.fingerprint(icc))
    run.record_profile_build(info)
    tab = _check_tab(s, ti3, icc)
    assert tab._show_colorimetry_on_controls(
        cc.Colorimetry.from_record(info["colorimetry"])) == ["M1"]


def test_a_spectral_file_build_keeps_todays_check(qapp, tmp_path,
                                                  monkeypatch):
    from workflow.profile_builder import ProfileParams
    s, work = _settings(tmp_path)
    run, ti3, icc = _run(work)
    info = {"builder": "colprof", "profile": icc.name}
    info.update(cc.record_for_build(ProfileParams(
        ti3_path=ti3, extra_args="-i /private/lamp/x.sp")))
    info.update(cc.fingerprint(icc))
    run.record_profile_build(info)
    assert "/private" not in run.meta_path.read_text(encoding="utf-8")
    tab = _check_tab(s, ti3, icc)
    runs, asked = _capture(monkeypatch, tab)
    tab._on_run()
    assert not asked and "-i" not in runs[0][1]
    assert "a spectral file for its colour settings (x.sp)" in \
        tab._log.toPlainText()
    assert "/private" not in tab._colour_record


def test_the_strips_file_and_the_guide_carry_the_mark(qapp, tmp_path):
    """Review m5: after "Check with my settings" the Refine_Strips file says
    so in a comment line (read past by every ChromIQ), and the Measure tab
    says so when Guided refinement starts from it."""
    from workflow.profcheck_runner import (parse_refine_strips,
                                           refine_strips_colour_note,
                                           write_refine_strips)
    s, work = _settings(tmp_path)
    _run_, ti3, icc = _run(work)
    tab = _check_tab(s, ti3, icc)
    tab._colour_insisted = {"built": cc.Colorimetry("2015_2"),
                            "check": cc.Colorimetry()}
    f = write_refine_strips(tmp_path, "x", [("A", 3.0), ("B", 2.5)],
                            colour_note=tab._colour_strips_note())
    assert parse_refine_strips(f) == ["A", "B"]
    note = refine_strips_colour_note(f)
    assert "observer 1931_2" in note and "observer 2015_2" in note
    plain = write_refine_strips(tmp_path, "y", [("A", 3.0)])
    assert refine_strips_colour_note(plain) == ""
    import inspect

    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure.start_guided_refinement)
    assert "refine_strips_colour_note(strips_file)" in src
    assert "These strips come from a check with other colour settings" in src


def test_verify_profile_records_its_colour_settings(qapp, tmp_path):
    """Review m2: the saved Verify_Profile report names the settings."""
    from types import SimpleNamespace

    from core.settings import AppSettings
    from tests.test_verify_profile_dialog import _PROFCHECK_LOG, _FakeChecker
    from ui.dialogs.tools_dialogs import VerifyProfileDialog
    _s, work = _settings(tmp_path)
    run, ti3, icc = _run(work)
    _record(run, icc, observer="2015_2")
    dlg = VerifyProfileDialog(runner=SimpleNamespace(is_running=False),
                              settings=AppSettings())
    dlg._profile, dlg._measured = icc, ti3
    fake = _FakeChecker(_PROFCHECK_LOG)
    dlg._checker = fake
    dlg._execute()
    assert fake.captured.observer == "2015_2"
    reports = list(run.dir.rglob("Verify_Profile_*"))
    assert reports, list(run.dir.rglob("*"))
    text = reports[0].read_text(encoding="utf-8")
    assert "Colour settings: observer CIE 2015 2°" in text
    assert "so the check uses the same settings" in text
    dlg.deleteLater()


def test_inspect_shows_the_settings_beside_its_score():
    import inspect

    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    assert "self._accuracy_colour_note = _note" in inspect.getsource(
        Ti3InfoDialog._run_profcheck)
    assert 'tr("Colour settings"), _cn' in inspect.getsource(
        Ti3InfoDialog._accuracy_section)


# ---------------------------------------------------------------------------
# last fix round (verification of 2026-11-21): V1, V4, V5
# ---------------------------------------------------------------------------

def _applycal_tab(tmp_path, qtbot, mode, monkeypatch, *, write: bool):
    from tests.test_the_new_profile_engine_is_one_switch import (
        _run_with_ti3, _tab)
    tab = _tab(tmp_path, profile_engine_beta=False)
    qtbot.addWidget(tab)
    run, ti3 = _run_with_ti3(tab, tmp_path)
    icc = ti3.with_suffix(".icc")
    icc.write_bytes(b"the run's profile" * 30)
    info = {"builder": "colprof", "profile": icc.name}
    info.update(cc.record_for_build(__import__(
        "workflow.profile_builder", fromlist=["x"]).ProfileParams(
            ti3_path=ti3, observer="2015_2")))
    info.update(cc.fingerprint(icc))
    run.record_profile_build(info)
    cal_file = tmp_path / "x.cal"
    cal_file.write_text("CAL", encoding="utf-8")
    tab._ac_cal_edit.setText(str(cal_file))
    tab._ac_in_edit.setText(str(icc))
    tab._ac_mode_combo.setCurrentIndex(tab._ac_mode_combo.findData(mode))
    monkeypatch.setattr(tab, "_confirm_not_calibrated_twice", lambda *_a: True)
    monkeypatch.setattr(tab, "_show_applycal_result_dialog", lambda *_a: None)

    def _fake_run(*, cal_path, in_icc, out_icc, mode, verbose, on_line,
                  on_finish):
        if write:
            Path(out_icc).write_bytes(b"freshly calibrated" * 30)
        on_finish(Path(out_icc))      # check mode reports the path too

    monkeypatch.setattr(tab._applycal_runner, "run", _fake_run)
    return tab, run


def test_check_calibration_records_nothing(tmp_path, qtbot, monkeypatch):
    """Verification V1: "Check calibration" writes no file but reports the
    run's calibrated.icc. An old calibrated.icc built otherwise must stay
    unknown and the record must not change."""
    import os
    tab, run = _applycal_tab(tmp_path, qtbot, "check", monkeypatch,
                             write=False)
    stale = run.calibrated_icc
    stale.write_bytes(b"an old calibrated copy, built with -i A -f" * 9)
    past = time.time() - 3600
    os.utime(stale, (past, past))
    before = run.load_meta().profile_build
    tab._on_applycal_run()
    assert run.load_meta().profile_build == before
    assert not cc.built_colorimetry(stale).known


def test_apply_calibration_records_the_file_it_wrote(tmp_path, qtbot,
                                                     monkeypatch):
    tab, run = _applycal_tab(tmp_path, qtbot, "apply", monkeypatch,
                             write=True)
    tab._on_applycal_run()
    got = cc.built_colorimetry(run.calibrated_icc)
    assert got.known and got.colorimetry.observer == "2015_2"


def test_apply_that_wrote_nothing_records_nothing(tmp_path, qtbot,
                                                  monkeypatch):
    """A successful apply whose output is the old file, untouched (the tool
    reported a path it did not write), records nothing."""
    import os
    tab, run = _applycal_tab(tmp_path, qtbot, "apply", monkeypatch,
                             write=False)
    old = run.calibrated_icc
    old.write_bytes(b"old" * 50)
    past = time.time() - 3600
    os.utime(old, (past, past))
    tab._on_applycal_run()
    assert not cc.built_colorimetry(old).known


def test_a_build_that_reports_a_file_it_did_not_write_records_no_settings(
        tmp_path, qtbot):
    import os
    from tests.test_the_new_profile_engine_is_one_switch import (
        _run_with_ti3, _tab)
    from workflow.profile_builder import ProfileParams
    tab = _tab(tmp_path, profile_engine_beta=False)
    qtbot.addWidget(tab)
    run, ti3 = _run_with_ti3(tab, tmp_path)
    icc = ti3.with_suffix(".icc")
    icc.write_bytes(b"an older profile" * 20)
    past = time.time() - 3600
    os.utime(icc, (past, past))
    tab._active_params = ProfileParams(ti3_path=ti3, observer="2015_2")
    tab._build_icc_before = cc.stamp(icc)
    tab._build_started_ns = time.time_ns()
    tab._note_a_colprof_build(icc)                   # nothing was written
    rec = run.load_meta().profile_build
    assert "colorimetry" not in rec and not cc.built_colorimetry(icc).known
    icc.write_bytes(b"the new profile" * 20)         # now it was written
    tab._note_a_colprof_build(icc)
    assert cc.built_colorimetry(icc).colorimetry.observer == "2015_2"


def test_a_record_without_a_hash_is_not_called_replaced(tmp_path):
    """Verification V4."""
    _s, work = _settings(tmp_path)
    run, _ti3, icc = _run(work)
    run.record_profile_build({"builder": "colprof", "profile": icc.name,
                              "colorimetry": {"observer": "2015_2"}})
    got = cc.built_colorimetry(icc)
    assert not got.known and got.reason == cc.UNKNOWN_OLD
    assert "does not identify the file" in got.why


def test_fwa_the_measurement_cannot_use_is_not_asked_about(
        qapp, tmp_path, monkeypatch, caplog):
    """Verification V5: built with -f; the checked measurement is refused
    -f by the FWA gate (it names no instrument); otherwise the settings
    match. The window would offer a choice that changes nothing, so it is
    not shown; the note says why FWA compensation is left out."""
    from workflow.profile_builder import ProfileParams
    s, work = _settings(tmp_path)
    run, ti3, icc = _run(work)
    info = {"builder": "colprof", "profile": icc.name}
    info.update(cc.record_for_build(ProfileParams(
        ti3_path=Path("elsewhere.ti3"), fwa_enabled=True)))
    info.update(cc.fingerprint(icc))
    run.record_profile_build(info)
    tab = _check_tab(s, ti3, icc)
    runs, asked = _capture(monkeypatch, tab, answer="profile")
    with caplog.at_level(logging.INFO):
        tab._on_run()
    assert not asked and runs
    assert "FWA compensation is left out" in tab._log.toPlainText()
    assert "FWA compensation left out: this measurement cannot use it" in \
        tab._colour_record
