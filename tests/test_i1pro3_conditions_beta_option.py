"""X-Rite i1Pro 3: keep M0, M1 and M2 from every scan (Preferences > Beta,
2026-11-15): the option, the Measure tab's command line and the Measure log.

* OFF (the default): the helper is started with exactly 4.3.40's command line;
* ON: ``--condition-dir <run>/conditions`` only for a profiling run, only for a
  helper that names the capability, and never for a verification, a
  calibration or the polariser;
* the helper's "conditions" events become one plain line in the Measure log;
* the Preferences row, its help and the window that asks before it goes on.
The helper and the driver are proved in test_i1pro3_conditions_engine.py and
test_i1pro3_conditions_driver.py.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_i1pro2_lights_beta_option import _Runner  # noqa: E402


def test_the_setting_is_off_by_default():
    from core.settings import DEFAULTS
    from workflow.i1pro3_conditions import SETTING
    assert DEFAULTS[SETTING] is False


def _args(tmp_path, monkeypatch, cdir, caps=("i1pro3_conditions",)):
    from workflow import chartread_engine
    from workflow.measure_manager import MeasureManager, MeasureParams
    monkeypatch.setattr(chartread_engine, "helper_caps",
                        lambda helper=None: frozenset(caps))
    monkeypatch.setattr(MeasureManager, "_refuse_system_port",
                        lambda self, *a, **k: False)
    runner = _Runner()
    m = MeasureManager(runner)
    p = MeasureParams(ti1_path=tmp_path / "chart.ti1",
                      engine_helper=tmp_path / "chromiq-chartread",
                      engine_condition_dir=cdir)
    m.start(p, lambda _l: None, lambda _c: None)
    return runner.calls[-1][1]


def test_off_starts_the_helper_with_exactly_todays_command_line(
        qapp, tmp_path, monkeypatch):
    off = _args(tmp_path, monkeypatch, None)
    assert "--condition-dir" not in off
    cdir = tmp_path / "conditions"
    on = _args(tmp_path, monkeypatch, cdir)
    k = on.index("--condition-dir")
    assert on[k + 1] == str(cdir) and cdir.is_dir()
    assert on[:k] + on[k + 2:] == off


def test_a_helper_that_does_not_know_it_is_not_given_it(
        qapp, tmp_path, monkeypatch):
    args = _args(tmp_path, monkeypatch, tmp_path / "conditions",
                 caps=("ruler_check",))
    assert "--condition-dir" not in args


@pytest.mark.parametrize("where,extra,wanted", [
    ("runs/run1", "", True),
    ("runs/run1", "-F 5", True),
    ("runs/run1", "-F u", True),
    ("runs/run1", "-F p", False),          # the polariser
    ("runs/run1/verifications", "", True),   # Basti, 2026-11-15
    ("cal", "", False),
])
def test_which_measurements_get_it(qapp, tmp_path, where, extra, wanted):
    from types import SimpleNamespace
    from ui.tabs.tab_measure import TabMeasure

    class _S(dict):
        def get(self, k, d=None):
            return super().get(k, d)

    fake = SimpleNamespace(_settings=_S(i1pro3_conditions_beta=True),
                           _is_verification_run=lambda: False)
    d = tmp_path / where
    d.mkdir(parents=True)
    p = SimpleNamespace(extra_args=extra, ti1_path=d / "chart.ti1")
    got = TabMeasure._condition_dir_for(fake, p)
    if wanted:
        assert got == d / "conditions"
        if where.endswith("verifications"):
            # one folder for every dated verification of the run
            from core.file_manager import Run
            assert got == Run.for_dir(d.parent).verification_condition_dir
    else:
        assert got is None
    fake._settings = _S(i1pro3_conditions_beta=False)
    assert TabMeasure._condition_dir_for(fake, p) is None


@pytest.mark.parametrize("ev,needle", [
    ({"event": "conditions", "active": True, "instrument": "i1pro3",
      "main": "M0", "extra": ["M1", "M2"]}, "also kept in M1"),
    ({"event": "conditions", "active": False, "why": "resume"},
     "started without them"),
    ({"event": "conditions", "active": False, "why": "write"},
     "could not be saved"),
])
def test_the_measure_log_says_it_once(ev, needle):
    from workflow.measure_manager import MeasureManager
    m = MeasureManager(_Runner())
    lines = []
    m._on_conditions_event(ev, lines.append)
    assert len(lines) == 1 and needle in lines[0], lines
    assert "—" not in lines[0]


def test_the_preferences_row_its_help_and_its_confirmation(qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from core.settings import AppSettings
    from ui.dialogs import settings_dialog as sd
    dlg = sd.SettingsDialog(AppSettings())
    try:
        box = dlg._i1pro3_conditions_check
        assert not box.isChecked()
        assert "(beta)" in box.text() and "i1Pro 3" in box.text()
        text = sd.i1pro3_conditions_help()
        for must in ("**M0**", "**M1**", "**M2**", "one instrument and one paper",
                     "FWA", "Nothing extra is sent", "**Default:** off"):
            assert must in text, must
        assert "—" not in text + sd.i1pro3_conditions_confirmation()
        monkeypatch.setattr(QMessageBox, "exec",
                            lambda self: QMessageBox.StandardButton.Cancel)
        box.click()
        assert not box.isChecked()
        monkeypatch.setattr(QMessageBox, "exec",
                            lambda self: QMessageBox.StandardButton.Ok)
        box.click()
        assert box.isChecked()
    finally:
        dlg.reject()
        dlg.deleteLater()


def test_a_verification_on_the_runs_own_chart_writes_to_the_verifications_folder(
        qapp, tmp_path):
    from types import SimpleNamespace
    from core.file_manager import Run
    from ui.tabs.tab_measure import TabMeasure

    class _S(dict):
        def get(self, k, d=None):
            return super().get(k, d)

    d = tmp_path / "runs/run1"
    d.mkdir(parents=True)
    fake = SimpleNamespace(_settings=_S(i1pro3_conditions_beta=True),
                           _is_verification_run=lambda: True)
    p = SimpleNamespace(extra_args="", ti1_path=d / "chart.ti1")
    assert (TabMeasure._condition_dir_for(fake, p)
            == Run.for_dir(d).verification_condition_dir
            == d / "verifications" / "conditions")
