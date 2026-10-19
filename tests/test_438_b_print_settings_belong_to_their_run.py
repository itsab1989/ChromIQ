"""Every Print Chart setting is the run's own (Knut, 2026-10-20).

Knut: *"When printing a chart in run1, where I define printer settings in Print
Chart tab, and then define another run (run2), with another paper and chart,
then define print settings in Print chart tab, and then go back to run 1, the
print settings on run1 changed to what I selected in run2 ... All the print
settings should be 100% individual per run and should never change on a run
based on settings made on a different run, while moving back and forth between
runs."*

Until 4.3.7 the printer and every option row (paper size, media type, tray,
quality ...) lived only on screen and in Save as Defaults, so whichever run was
looked at last decided what every run showed and printed with, and a restart
put all of them back on the saved defaults. per_target_settings.md §5a.

The tab is driven with a stand-in for CUPS (two queues with two option rows
each), so nothing here can reach a printer.
"""
from __future__ import annotations

import os
from collections import OrderedDict

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (                     # noqa: E402
    RUN_TYPE_CALIBRATION, RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402

QA, QB = "Capture_A", "Capture_B"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeCups:
    """Two queues; each offers a paper size and a media type row."""

    def detect_printers(self):
        return [QA, QB]

    def query_options(self, printer):
        return OrderedDict([
            ("PageSize", ("Page Size", [("A4", "A4"), ("Letter", "Letter"),
                                        ("A3", "A3")])),
            ("MediaType", ("Media Type", [("Plain", "Plain"),
                                          ("Glossy", "Glossy"),
                                          ("Matte", "Matte")])),
        ])

    def get_valid_option_values(self, printer, preceding, labels, opt,
                                all_vals, all_pairs):
        return list(all_vals)              # no constraints between the rows

    def __getattr__(self, name):            # anything else: nothing known
        return lambda *a, **k: None


def _env(tmp_path, *, calibration=False):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    s.set("use_native_print_dialog", False)
    if calibration:
        s.set("calibration_mode", True)
    fm = FileManager(s)
    proj = Project.create(tmp_path / "P", "P")
    proj.current_run().ensure_dir()
    proj.new_run().ensure_dir()                       # run2
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    if calibration:
        ctl.set_calibration_allowed(True)
    ctl.set_profile_run("run1")
    return s, fm, ctl


def _tab(s, ctl):
    from ui.tabs.tab_print import TabPrint
    tab = TabPrint(s)
    tab._module = _FakeCups()
    tab.set_target_controller(ctl)
    return tab


def _shown(tab):
    """What the tab's first showing does: read the printer list."""
    tab.reload_printers()


def _choose(tab, printer, **opts):
    cb = tab._printer_combo
    cb.setCurrentIndex(cb.findData(printer))          # the user's pick
    for name, value in opts.items():
        combo = tab._option_combos[name]
        combo.setCurrentIndex(combo.findData(value))


def _screen(tab):
    return (tab._printer_combo.currentData(),
            {k: c.currentData() for k, c in tab._option_combos.items()})


def _switch(tab, ctl, *, run=None, run_type=None):
    """A target change as MainWindow makes it: the outgoing target is written
    when the pulldown opens (Q-1), the incoming one loaded when chosen."""
    tab.save_target_settings()
    if run_type is not None:
        ctl.set_run_type(run_type)
    if run is not None:
        ctl.set_profile_run(run)
    tab.load_target_settings()


def _stored(store):
    return dict(store.load_meta().print_settings or {})


# ----------------------------------------------------------------------
def test_knuts_steps_each_run_keeps_its_own(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    tab.load_target_settings()
    _shown(tab)
    _choose(tab, QA, PageSize="A4", MediaType="Glossy")          # run1
    _switch(tab, ctl, run="run2")
    # run2 has nothing stored: the saved defaults (none here), NOT run1's
    assert _screen(tab) != (QA, {"PageSize": "A4", "MediaType": "Glossy"})
    _choose(tab, QA, PageSize="Letter", MediaType="Matte")       # run2
    _switch(tab, ctl, run="run1")
    assert _screen(tab) == (QA, {"PageSize": "A4", "MediaType": "Glossy"})
    _switch(tab, ctl, run="run2")
    assert _screen(tab) == (QA, {"PageSize": "Letter", "MediaType": "Matte"})
    _switch(tab, ctl, run="run1")
    assert _screen(tab) == (QA, {"PageSize": "A4", "MediaType": "Glossy"})

    proj = fm.project()
    assert _stored(proj.run("run1"))["printer_options"] == {
        QA: {"PageSize": "A4", "MediaType": "Glossy"}}
    assert _stored(proj.run("run2"))["printer_options"] == {
        QA: {"PageSize": "Letter", "MediaType": "Matte"}}


def test_a_run_keeps_its_own_printer(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    tab.load_target_settings()
    _shown(tab)
    _choose(tab, QA, PageSize="A4")
    _switch(tab, ctl, run="run2")
    _choose(tab, QB, PageSize="A3", MediaType="Matte")
    _switch(tab, ctl, run="run1")
    assert _screen(tab)[0] == QA
    assert _screen(tab)[1]["PageSize"] == "A4"
    _switch(tab, ctl, run="run2")
    assert _screen(tab) == (QB, {"PageSize": "A3", "MediaType": "Matte"})


def test_a_restart_opens_each_run_on_its_own(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    tab.load_target_settings()
    _shown(tab)
    _choose(tab, QB, PageSize="A3", MediaType="Glossy")
    tab.save_target_settings()                       # app quit (W6)

    # a new window: the run is loaded before the tab is first shown ...
    tab2 = _tab(s, ctl)
    tab2.load_target_settings()
    _shown(tab2)
    assert _screen(tab2) == (QB, {"PageSize": "A3", "MediaType": "Glossy"})
    # ... and after it
    tab3 = _tab(s, ctl)
    _shown(tab3)
    tab3.load_target_settings()
    assert _screen(tab3) == (QB, {"PageSize": "A3", "MediaType": "Glossy"})


def test_looking_at_a_run_stores_no_printer(qapp, tmp_path):
    """§4 S4/S9: a run with nothing stored that is only looked at keeps
    nothing stored, so it goes on following the saved defaults."""
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    tab.load_target_settings()
    _shown(tab)
    tab.save_target_settings()
    assert "printer" not in _stored(fm.project().run("run1"))


def test_an_old_run_opens_on_the_saved_defaults(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path)
    s.set("last_printer", QB)
    s.set(f"print_opts_{QB}", "PageSize=Letter|MediaType=Matte")
    tab = _tab(s, ctl)
    _shown(tab)
    tab.load_target_settings()
    assert _screen(tab) == (QB, {"PageSize": "Letter", "MediaType": "Matte"})


def test_a_hidden_tab_never_files_one_runs_values_onto_another(qapp, tmp_path):
    """Close Project asks every tab to save. The Print tab, left on run1 and
    not shown since the bar moved to run2, must not write run1's values into
    run2 (§2.0)."""
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    tab.load_target_settings()
    _shown(tab)
    _choose(tab, QA, PageSize="A4", MediaType="Glossy")
    tab.save_target_settings()
    ctl.set_profile_run("run2")                      # no load: tab hidden
    assert tab.save_target_settings() is False
    assert _stored(fm.project().run("run2")) == {}


def test_a_new_run_starts_on_the_run_it_was_made_from(qapp, tmp_path):
    """§4a: a run made since the tab last loaded starts on the settings of
    the run that was on screen, and keeps them."""
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    tab.load_target_settings()
    _shown(tab)
    _choose(tab, QB, PageSize="A3", MediaType="Matte")
    tab.save_target_settings()
    run3 = fm.project().new_run()                    # e.g. Generate on New run
    run3.ensure_dir()
    _switch(tab, ctl, run=run3.id)
    assert _screen(tab) == (QB, {"PageSize": "A3", "MediaType": "Matte"})
    tab.save_target_settings()
    assert _stored(fm.project().run(run3.id))["printer"] == QB
    # an EXISTING run with nothing stored is not seeded
    _switch(tab, ctl, run="run2")
    assert _screen(tab)[1] != {"PageSize": "A3", "MediaType": "Matte"}


def test_a_verification_follows_its_run_until_given_its_own(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    tab.load_target_settings()
    _shown(tab)
    _choose(tab, QA, PageSize="A4", MediaType="Glossy")
    _switch(tab, ctl, run_type=RUN_TYPE_VERIFICATION)
    assert _screen(tab) == (QA, {"PageSize": "A4", "MediaType": "Glossy"})
    run1 = fm.project().run("run1")
    from core.file_manager import Run
    vstore = Run.for_dir(run1.verifications_dir)
    tab.save_target_settings()
    assert "printer" not in _stored(vstore)          # still following
    _choose(tab, QA, PageSize="A4", MediaType="Matte")
    _switch(tab, ctl, run_type=RUN_TYPE_PROFILING)
    assert _screen(tab)[1]["MediaType"] == "Glossy"  # the run is untouched
    _switch(tab, ctl, run_type=RUN_TYPE_VERIFICATION)
    assert _screen(tab)[1]["MediaType"] == "Matte"


def test_the_calibration_keeps_its_own(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path, calibration=True)
    fm.project().calibration.dir.mkdir(parents=True, exist_ok=True)
    tab = _tab(s, ctl)
    tab.load_target_settings()
    _shown(tab)
    _choose(tab, QA, PageSize="A4", MediaType="Glossy")
    _switch(tab, ctl, run_type=RUN_TYPE_CALIBRATION)
    _choose(tab, QB, PageSize="Letter", MediaType="Plain")
    _switch(tab, ctl, run_type=RUN_TYPE_PROFILING)
    assert _screen(tab) == (QA, {"PageSize": "A4", "MediaType": "Glossy"})
    _switch(tab, ctl, run_type=RUN_TYPE_CALIBRATION)
    assert _screen(tab) == (QB, {"PageSize": "Letter", "MediaType": "Plain"})
    assert _stored(fm.project().calibration)["printer"] == QB


def test_an_old_calibration_meta_still_loads():
    from core.file_manager import CalibrationMeta
    m = CalibrationMeta.from_dict({"description": "x"})
    assert m.print_settings == {}


# ---------------------------------------------------- the demo-style test
def test_two_runs_switched_back_and_forth_in_the_main_window(qapp, tmp_path,
                                                            monkeypatch):
    """Knut's steps through MainWindow's own events: the bar's pulldown
    write (Q-1), the visible tab's reload (L3), a tab change (W6/L1)."""
    import ui.tabs.tab_print as tp
    monkeypatch.setattr(tp, "PrintModule", _FakeCups)
    from ui.main_window import MainWindow

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    s.set("use_native_print_dialog", False)
    win = MainWindow(s)
    try:
        qapp.processEvents()
        win._file_mgr.set_target_name("Two Runs")
        proj = win._file_mgr.project()
        proj.current_run().ensure_dir()
        proj.new_run().ensure_dir()
        ctl = win._target_ctl
        ctl.set_profile_run("run1")
        qapp.processEvents()
        tab = win._tab_print
        tab.reload_printers()
        win._tabs.setCurrentWidget(tab)
        qapp.processEvents()

        _choose(tab, QA, PageSize="A4", MediaType="Glossy")
        ctl.set_profile_run("run2"); qapp.processEvents()
        _choose(tab, QB, PageSize="Letter", MediaType="Matte")
        ctl.set_profile_run("run1"); qapp.processEvents()
        assert _screen(tab) == (QA, {"PageSize": "A4", "MediaType": "Glossy"})
        # leave the tab, change run elsewhere, come back
        win._tabs.setCurrentWidget(win._tab_chart); qapp.processEvents()
        ctl.set_profile_run("run2"); qapp.processEvents()
        win._tabs.setCurrentWidget(tab); qapp.processEvents()
        assert _screen(tab) == (QB, {"PageSize": "Letter", "MediaType": "Matte"})
        # Close Project from another tab must not move run2's values to run1
        win._tabs.setCurrentWidget(win._tab_chart); qapp.processEvents()
        ctl.set_profile_run("run1"); qapp.processEvents()
        win.close_current_project(); qapp.processEvents()
        assert _stored(proj.run("run1"))["printer"] == QA
        assert _stored(proj.run("run2"))["printer"] == QB
    finally:
        win.close()
