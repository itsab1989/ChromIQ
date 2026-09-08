"""The Report limits window (#182): shape A, editable where Knut ruled it,
read-only ISO columns, per-run column memory, per-column restore, the buffered
Preferences door and the write-as-edited report door, and the "This run" column.

Offscreen: enabled/values/round-trips are reliable there; visibility and
geometry are proven on screen by the driver, not here.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel          # noqa: E402

from core.file_manager import Project                     # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from ui.widgets import NoScrollDoubleSpinBox              # noqa: E402
from workflow import run_compliance as rc                 # noqa: E402
from workflow.compliance_sets import Limit, factory_limits  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings(tmp_path) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


def _dlg(qapp, tmp_path, **kw):
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    s = kw.pop("settings", None) or _settings(tmp_path)
    return s, ThresholdsDialog(s, None, **kw)


def _cell(dlg, col, row_id):
    return dlg._cells[(col, row_id)]


def test_editable_and_read_only_columns_follow_the_rulings(qapp, tmp_path):
    s, dlg = _dlg(qapp, tmp_path)
    try:
        # ChromIQ's three sets and the two Custom sets have spin boxes …
        for col in ("chromiq_default", "chromiq_tight", "chromiq_quick",
                    "custom_iso_12647_7", "custom_iso_12647_8"):
            assert isinstance(_cell(dlg, col, "all_de00_avg"), NoScrollDoubleSpinBox), col
        # … the ISO columns are labels (read-only), reading ? until S-2
        for col in ("iso_12647_7", "iso_12647_8"):
            w = _cell(dlg, col, "all_de00_avg")
            assert isinstance(w, QLabel) and w.text() == "?", col
        # a row a set defines no limit for reads – ; an unmeasurable row ✕ / –
        assert _cell(dlg, "iso_12647_7", "best95_de00_avg").text() == "–"
        assert _cell(dlg, "iso_12647_7", "substrate_gloss_class").text() == "✕"
        assert _cell(dlg, "chromiq_default", "substrate_gloss_class").text() == "–"
        # a should-limit shows its brackets on the spin box
        sb = _cell(dlg, "chromiq_default", "grey_balance_neutral_ramp_avg")
        assert sb.prefix() == "(" and sb.suffix() == ")" and sb.value() == 1.5
        # no "This run" column without a run
        assert not any(c == "__run__" for c, _r in dlg._cells)
    finally:
        dlg.deleteLater()


def test_the_report_door_writes_overrides_as_they_are_edited(qapp, tmp_path):
    s, dlg = _dlg(qapp, tmp_path)
    try:
        sb = _cell(dlg, "chromiq_default", "all_de00_avg")
        sb.setValue(2.7)
        assert s.get_compliance_overrides() == {"chromiq_default": {"all_de00_avg": 2.7}}
        # back to the factory number removes the override instead of storing it
        sb.setValue(2.0)
        assert s.get_compliance_overrides() == {}
        # 0 means "no limit" (CH-21) and shows –
        sb.setValue(0.0)
        assert sb.text() == "–"
        assert s.get_compliance_overrides() == {"chromiq_default": {"all_de00_avg": None}}
        assert dlg.value_of("chromiq_default", "all_de00_avg").kind == "none"
    finally:
        dlg.deleteLater()


def test_the_preferences_door_edits_a_buffer_not_the_settings(qapp, tmp_path):
    """CH-19: from Preferences, edits are kept when Save is pressed and dropped
    with Cancel, so the window must not write the settings itself."""
    buf = {"overrides": {}, "default_set": "chromiq_default"}
    s, dlg = _dlg(qapp, tmp_path, buffer=buf)
    try:
        _cell(dlg, "chromiq_tight", "all_de00_max").setValue(1.2)
        assert buf["overrides"] == {"chromiq_tight": {"all_de00_max": 1.2}}
        assert s.get_compliance_overrides() == {}                 # untouched
        dlg._default_radios["chromiq_quick"].setChecked(True)
        assert buf["default_set"] == "chromiq_quick"
        assert s.get("compliance_default_set") == "chromiq_default"
    finally:
        dlg.deleteLater()


def test_restore_this_column_touches_that_column_only(qapp, tmp_path):
    s = _settings(tmp_path)
    s.set_compliance_overrides({"chromiq_default": {"all_de00_avg": 2.9},
                                "chromiq_tight": {"all_de00_avg": 0.7}})
    s, dlg = _dlg(qapp, tmp_path, settings=s)
    try:
        assert _cell(dlg, "chromiq_default", "all_de00_avg").value() == 2.9
        btn = next(w for w in dlg._column_widgets["chromiq_default"]
                   if w.__class__.__name__ == "QPushButton")
        btn.click()
        assert _cell(dlg, "chromiq_default", "all_de00_avg").value() == 2.0
        assert s.get_compliance_overrides() == {"chromiq_tight": {"all_de00_avg": 0.7}}
    finally:
        dlg.deleteLater()


def test_column_visibility_is_stored_per_run_or_in_preferences(qapp, tmp_path):
    # Preferences door: the settings key
    s, dlg = _dlg(qapp, tmp_path)
    try:
        dlg._column_checks["iso_12647_7"].setChecked(False)
        shown = json.loads(s.get("compliance_columns_shown"))
        assert "iso_12647_7" not in shown and "chromiq_default" in shown
        assert not _cell(dlg, "iso_12647_7", "all_de00_avg").isVisibleTo(dlg)
    finally:
        dlg.deleteLater()
    # report door: the run's meta.json, and Preferences untouched (CH-18)
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    s2 = _settings(tmp_path / "two")
    s2, dlg2 = _dlg(qapp, tmp_path / "two", settings=s2, run=run)
    try:
        dlg2._column_checks["chromiq_quick"].setChecked(False)
        assert "chromiq_quick" not in run.load_meta().compliance_columns
        assert "chromiq_default" in run.load_meta().compliance_columns
        assert s2.get("compliance_columns_shown") == ""
    finally:
        dlg2.deleteLater()
    # …and it is read back next time
    s3, dlg3 = _dlg(qapp, tmp_path / "three", run=run)
    try:
        assert not dlg3._column_checks["chromiq_quick"].isChecked()
        assert dlg3._column_checks["chromiq_default"].isChecked()
    finally:
        dlg3.deleteLater()


def test_this_run_column_is_locked_until_unlocked_and_written_once_on_close(qapp, tmp_path):
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    rc.bind_run(run, "chromiq_default", {})
    # locked: labels, and a note saying how to unlock
    s, dlg = _dlg(qapp, tmp_path, run=run, run_editable=False)
    try:
        w = _cell(dlg, "__run__", "all_de00_avg")
        from PyQt6.QtCore import QLocale
        # read-only cells use the spin boxes' locale (2,00 on a German machine)
        assert isinstance(w, QLabel) and w.text() == QLocale.system().toString(2.0, "f", 2)
        notes = [x.text() for x in dlg._column_widgets["__run__"] if isinstance(x, QLabel)]
        assert any("Unlock" in t for t in notes)
        dlg.accept()
        assert dlg.run_limits_changed is False
    finally:
        dlg.deleteLater()
    # unlocked: spin boxes; the copy is written ONCE, on close (CH-29)
    s, dlg = _dlg(qapp, tmp_path / "b", run=run, run_editable=True)
    try:
        sb = _cell(dlg, "__run__", "all_de00_avg")
        assert isinstance(sb, NoScrollDoubleSpinBox)
        sb.setValue(2.6)
        assert run.load_meta().compliance_thresholds["all_de00_avg"] == 2.0   # not yet
        dlg.accept()
        assert dlg.run_limits_changed is True
        assert run.load_meta().compliance_thresholds["all_de00_avg"] == 2.6
        assert rc.run_limits(run, {}).edited
    finally:
        dlg.deleteLater()
    # Restore this column on "This run" copies the set back
    s, dlg = _dlg(qapp, tmp_path / "c", run=run, run_editable=True)
    try:
        btn = next(w for w in dlg._column_widgets["__run__"]
                   if w.__class__.__name__ == "QPushButton")
        btn.click()
        assert _cell(dlg, "__run__", "all_de00_avg").value() == 2.0
        dlg.accept()
        assert run.load_meta().compliance_thresholds["all_de00_avg"] == 2.0
    finally:
        dlg.deleteLater()


def test_no_lambda_or_partial_is_connected_to_a_child_signal():
    """The segfault rule (CLAUDE.md): a closure capturing self on a child
    widget's signal. Every connect in this window names a bound method."""
    import inspect
    import re
    from ui.dialogs import thresholds_dialog as td
    src = inspect.getsource(td)
    for m in re.finditer(r"\.connect\(([^)]*)\)", src):
        arg = m.group(1)
        assert "lambda" not in arg and "partial" not in arg, arg


def test_a_default_radio_exists_only_for_selectable_sets(qapp, tmp_path):
    s, dlg = _dlg(qapp, tmp_path)
    try:
        assert set(dlg._default_radios) == {"chromiq_default", "chromiq_tight",
                                            "chromiq_quick"}
        assert dlg._default_radios["chromiq_default"].isChecked()
        assert factory_limits("iso_12647_7")["all_de00_avg"] == Limit.unknown()
    finally:
        dlg.deleteLater()


def test_this_run_recommendation_survives_a_trip_through_zero(qapp, tmp_path):
    """F4: turning a bracketed cell to 0 and back must keep it a recommendation."""
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    rc.bind_run(run, "chromiq_default", {})
    s, dlg = _dlg(qapp, tmp_path, run=run, run_editable=True)
    try:
        sb = _cell(dlg, "__run__", "grey_balance_neutral_ramp_avg")
        sb.setValue(0.0)
        sb.setValue(2.0)
        assert dlg._run_limits["grey_balance_neutral_ramp_avg"] == Limit.should(2.0)
        dlg.accept()
        assert run.load_meta().compliance_thresholds["grey_balance_neutral_ramp_avg"] == [2.0, "should"]
    finally:
        dlg.deleteLater()


def test_column_choice_from_preferences_waits_in_the_buffer(qapp, tmp_path):
    """F12: from Preferences, Cancel must drop a hidden column like any edit."""
    buf = {"overrides": {}, "default_set": "chromiq_default"}
    s, dlg = _dlg(qapp, tmp_path, buffer=buf)
    try:
        dlg._column_checks["iso_12647_7"].setChecked(False)
        assert "iso_12647_7" not in json.loads(buf["columns"])
        assert s.get("compliance_columns_shown") == ""
    finally:
        dlg.deleteLater()
    # …and a buffer with a choice is what the window opens on next time
    s2, dlg2 = _dlg(qapp, tmp_path / "b", buffer=buf)
    try:
        assert not dlg2._column_checks["iso_12647_7"].isChecked()
    finally:
        dlg2.deleteLater()
