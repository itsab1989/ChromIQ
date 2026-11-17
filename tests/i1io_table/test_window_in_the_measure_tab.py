"""Build step 9: START MEASUREMENT on the Measure tab and the table window.

* Beta ON, a profile run's chart for an i1iO 2 with an i1Pro 2 (its side file says so): START
  opens the table window, in Manual and in Guided, with the mode's own chartread arguments.
* Beta ON, a chart without such a side file (an i1iO 3, a bare "i1iO", a calibration chart):
  today's Start window, untouched.
* Beta OFF: nothing of the window is read or imported; Start is as before.
* The window's Save is announced as after a hand measurement (``measure_finished``)."""
from __future__ import annotations

import json
import sys

import pytest

from core.file_manager import Project
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_reading import small_sheet
from tests.i1io_table.window_person import WindowPerson
from tests.i1io_table.window_sim import WindowSim


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabMeasure(ArgyllRunner(s), s)
    yield t
    w = getattr(t, "_table_window", None)
    if w is not None:
        w._finished = True
        w.close()
    t.close()
    t.deleteLater()


@pytest.fixture
def beta(monkeypatch):
    import workflow.i1io.support as sup
    sup.set_enabled_for_this_process(True)
    yield
    sup.set_enabled_for_this_process(None)


def table_run(tmp_path, sheet=None, *, side=True, head="i1Pro 2"):
    sheet = dict(sheet or small_sheet())
    sheet["head_model"] = head
    proj = Project.create(tmp_path / "Table-Target", "Table-Target")
    run = proj.current_run()
    run.ensure_dir()
    text = RS.chart_ti2_text(sheet).replace('TARGET_INSTRUMENT "X-Rite i1 Pro 2"',
                                            'TARGET_INSTRUMENT "X-Rite i1iO"')
    run.chart_ti2.write_text(text, encoding="ascii")
    run.artefact(".ti1").write_text(text.replace("CTI2", "CTI1", 1), encoding="ascii")
    if side:
        run.i1io_side_file.write_text(json.dumps(sheet), encoding="utf-8")
    return run, sheet


def start(tab, run, monkeypatch, sim=None):
    import ui.i1io_table_window as W
    sim = sim or WindowSim()
    monkeypatch.setattr(W, "JOB_FACTORY", sim.factory)
    monkeypatch.setattr(W, "USB_STATUS", lambda: (True, ""))
    tab._settings.set(W.CONSENT_KEY, W.CONSENT_VERSION)
    tab.set_ti1_path(run.artefact(".ti1"))
    monkeypatch.setattr(tab, "_blocked_by_new_run", lambda: False)
    monkeypatch.setattr(tab, "_i1io_not_yet_window",
                        lambda: pytest.fail("the table chart got today's Start window"))
    tab._on_start()
    return sim


@pytest.mark.parametrize("mode", ["manual", "guided"])
def test_start_opens_the_table_window_in_both_modes(tab, beta, tmp_path, monkeypatch, qtbot,
                                                   mode):
    monkeypatch.setattr(tab, "_current_mode", lambda: mode)
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch)
    win = tab._table_window
    assert win is not None and win.isVisible() and win._mode == mode
    assert win._chart_args[:3] == ["-v", "-c", "1"]                # the mode's own args
    assert win._chart_args[-1].endswith("Table-Target")
    finished = []
    tab.measure_finished.connect(finished.append)
    p = WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=15000))
    p.drive_until("end_of_session")
    p.press("Save and stop")
    assert finished == [run.measurement_ti3]
    assert "[OK] Measurement complete." in tab._log.toPlainText()


def test_a_chart_without_the_side_file_keeps_todays_start_window(tab, beta, tmp_path,
                                                                 monkeypatch):
    run, sheet = table_run(tmp_path, side=False)
    shown = []
    monkeypatch.setattr(tab, "_i1io_window", lambda title, body: shown.append(title))
    tab.set_ti1_path(run.artefact(".ti1"))
    assert tab._started_the_table_drive() is False
    assert tab._refused_as_an_i1io_chart() is True and len(shown) == 1


def test_an_i1io_3_chart_keeps_todays_start_window(tab, beta, tmp_path, monkeypatch):
    run, sheet = table_run(tmp_path, head="i1Pro 3")
    tab.set_ti1_path(run.artefact(".ti1"))
    assert tab._started_the_table_drive() is False


def test_beta_off_reads_nothing_and_imports_no_window(tab, tmp_path, monkeypatch):
    import workflow.i1io.support as sup
    sup.set_enabled_for_this_process(False)
    try:
        run, sheet = table_run(tmp_path)
        tab.set_ti1_path(run.artefact(".ti1"))

        def asked(*_a, **_k):
            raise AssertionError("a chart was read for the table with the Beta off")
        monkeypatch.setattr(sup, "chart_names_i1io", asked)
        was = "ui.i1io_table_window" in sys.modules
        assert tab._started_the_table_drive() is False
        assert ("ui.i1io_table_window" in sys.modules) is was
    finally:
        sup.set_enabled_for_this_process(None)


def test_a_run_with_a_measurement_asks_the_hand_paths_replace_question_first(
        tab, beta, tmp_path, monkeypatch, qtbot):
    run, sheet = table_run(tmp_path)
    run.measurement_ti3.write_text("CTI3\n", encoding="ascii")
    asked = []
    monkeypatch.setattr(tab, "_confirm_replacing_measurement",
                        lambda: asked.append(1) or False)
    start(tab, run, monkeypatch)
    assert asked == [1] and getattr(tab, "_table_window", None) is None


def test_the_preferences_box_is_there_only_with_the_beta_on(qapp, tmp_path, monkeypatch):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    import workflow.i1io.support as sup
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    for on in (False, True):
        sup.set_enabled_for_this_process(on)
        try:
            dlg = SettingsDialog(s)
            box = getattr(dlg, "_i1io_ask_check", None)
            assert (box is not None) is on
            if on:
                assert box.isChecked()
                box.setChecked(False)
                dlg._save() if hasattr(dlg, "_save") else None
            dlg.deleteLater()
        finally:
            sup.set_enabled_for_this_process(None)
