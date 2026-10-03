"""A preset can be saved from a calibration chart and loaded again (#182).

Knut, #182 5965186237 (2026-10-03), answering whether the preset box should be
greyed out in Run type = Calibration: *"A user may want to create a preset for
a Calibration chart made."* So in Calibration the preset box stays live: the
save button stores the calibration setup, and picking that preset later in
Calibration applies its settings and builds targen's calibration chart into
cal/. It never attaches a patch set (even one saved with the preset), never
meets the refusal the built-in profiling charts get, and never writes into a
profiling run.
"""
from __future__ import annotations

import pytest

from core.measurement_target import RUN_TYPE_CALIBRATION
from tests._cal_target_fixture import (Refusals, fingerprint, make_window,
                                       show_run, write_run_chart)

NAME = "My-calibration-setup"


@pytest.fixture
def win(qapp, tmp_path):
    w = make_window(qapp, tmp_path)
    run1 = w._file_mgr.project().current_run()
    write_run_chart(run1, given=True)
    show_run(w, qapp, run1.id)
    yield w, run1
    w.close()


def _steps(tc):
    return next(pw for pw in tc._manual_widgets["targen"] if pw.flag == "-s")


def _save_preset_in_calibration(w, qapp, monkeypatch, tmp_path):
    """The real Save Preset window, answered the way a user does: a name, and
    "Build from the currently loaded patch set" ticked (the worst case)."""
    from PyQt6.QtWidgets import QCheckBox, QDialog, QLineEdit

    tc = w._tab_chart
    w._target_ctl.set_run_type(RUN_TYPE_CALIBRATION)
    qapp.processEvents()
    assert tc._calibration_selected()
    _steps(tc).set_value(25)
    # The calibration chart on screen, so the attach box is offered.
    cal_ti1 = tmp_path / "cal-shown.ti1"
    cal_ti1.write_text(
        'CTI1\n\nORIGINATOR "Argyll targen"\nCOLOR_REP "iRGB"\n\n'
        "NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\n"
        "END_DATA_FORMAT\n\nNUMBER_OF_SETS 1\nBEGIN_DATA\n1 100 100 100\n"
        "END_DATA\n", encoding="utf-8")
    tc._current_ti1_path = cal_ti1

    def _answer(dlg):
        edits = [e for e in dlg.findChildren(QLineEdit)]
        for cb in dlg.findChildren(QCheckBox):
            if "attach its .ti1" in cb.text() and cb.isEnabled():
                cb.setChecked(True)
            if "Add a descriptive prefix" in cb.text():
                cb.setChecked(False)
        edits[0].setText(NAME)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", _answer)
    tc._on_preset_save()
    monkeypatch.undo()
    assert tc._preset_combo.findData(NAME) >= 0 \
        or tc._preset_combo.findText(NAME) >= 0, "the preset was not saved"


def test_a_preset_saved_in_calibration_loads_there_and_builds_into_cal(
        win, qapp, monkeypatch, tmp_path):
    w, run1 = win
    tc = w._tab_chart
    _save_preset_in_calibration(w, qapp, monkeypatch, tmp_path)

    built = {"targen": [], "from_ti1": []}
    monkeypatch.setattr(tc._creator, "generate",
                        lambda params, *a, **k: built["targen"].append(params))
    monkeypatch.setattr(
        tc._creator, "load_ti1_and_generate_preview",
        lambda ti1, params, *a, **k: built["from_ti1"].append(ti1))
    refusals = Refusals()
    monkeypatch.setattr("ui.tabs.tab_chart.InfoDialog", refusals)
    monkeypatch.setattr(type(tc), "_confirm_displacing_results",
                        lambda self, *a, **k: True)
    monkeypatch.setattr(type(tc), "_handle_target_rename",
                        lambda self, *a, **k: True)

    # Later: something else on screen, then the preset is picked again.
    _steps(tc).set_value(20)
    before = fingerprint(run1.dir)
    combo = tc._preset_combo
    ix = combo.findData(NAME)
    if ix < 0:
        ix = combo.findText(NAME)
    combo.blockSignals(True)
    combo.setCurrentIndex(ix)
    combo.blockSignals(False)
    tc._on_preset_selected(ix)
    qapp.processEvents()

    assert refusals.shown == [], f"the calibration preset was refused: {refusals.shown}"
    assert str(_steps(tc).get_raw_value()) in ("25", "25.0"), \
        "the preset's Single Channel Steps did not come back"
    assert tc._preset_ti1_path is None and not tc._knut_active \
        and not tc._tc918_active, "a patch set was bound in Calibration"
    assert all(wd.isEnabled() for wd in tc._manual_targen_content), \
        "the targen panel is locked in Calibration"

    tc._on_generate()
    assert built["from_ti1"] == [], "the attached patch set was laid out"
    # A preset saved with "Generate immediately" builds on the pick as well;
    # every build there is the calibration chart.
    assert built["targen"], "targen was not asked for the calibration chart"
    assert all(p.cal_target is True for p in built["targen"]), \
        "a build was not for cal/"
    assert fingerprint(run1.dir) == before, "run1's files changed"
