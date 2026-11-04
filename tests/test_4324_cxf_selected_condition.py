"""4.3.24: i1Profiler's own choice of measurement condition is preselected,
and a file that holds only some of M0, M1 and M2 imports under each
combination.

jctay (printerknowledge, 2026-11-04) saved one i1Pro 3 measurement three
times in i1Profiler 3.8.5, with M0, M1 and M2 chosen: the files differ only in
``SelectedMeasurementCondition="0"``, ``"1"`` and ``"2"``. His files that hold
only some conditions agree with that (M0 only "0", M1 only "1", M2 only "2",
M0+M1 "0", M1+M2 "1"), so the number names the condition itself, not its
place among the conditions the file holds. 4.3.23 mapped no number and
preselected M1.

Every fixture is invented and only reproduces the structure of his files
(measurement objects first, then the Target objects, i1Profiler's Prism
CustomAttributes with ``MeasurementDevice`` and the selected condition).
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M                    # noqa: E402
from workflow.fwa_gate import fwa_refusal_for_file                  # noqa: E402
from workflow.measurement_condition import read_condition            # noqa: E402
from workflow.reference_convert import (                             # noqa: E402
    ReferenceConvertError, condition_from_label, cxf_conditions,
    cxf_measurement_to_ti3)
from workflow.ti3_merge import condition_check                       # noqa: E402

_NS = "http://colorexchangeformat.com/CxF3-core"
_N = 12


def _native(path: Path, conditions, selected) -> Path:
    """An invented i1Profiler .mxf laid out like jctay's native files."""
    lam = np.arange(36)
    objs = []
    for c in conditions:
        lift = {"M0": 1.0, "M1": 1.1, "M2": 0.9}[c]
        for i in range(1, _N + 1):
            v = 0.05 + 0.8 * np.exp(-((lam - 3 * i) / 6.0) ** 2)
            v[:10] *= lift
            s = " ".join(f"{x:.6f}" for x in v)
            objs.append(
                f'<cc:Object ObjectType="{c}_Measurement" '
                f'Name="{c}_Measurement{i}" Id="{c}{i}">'
                f'<cc:CreationDate>2026-11-02T06:27:39Z</cc:CreationDate>'
                f'<cc:ColorValues><cc:ReflectanceSpectrum StartWL="380" '
                f'ColorSpecification="{c}_Measurement_spec">{s}'
                f'</cc:ReflectanceSpectrum></cc:ColorValues></cc:Object>')
    for i in range(1, _N + 1):
        objs.append(
            f'<cc:Object ObjectType="Target" Name="Target{i}" Id="t{i}">'
            f'<cc:DeviceColorValues><cc:ColorRGB ColorSpecification="Unknown">'
            f'<cc:R>{(i * 20) % 256}</cc:R><cc:G>{(i * 50) % 256}</cc:G>'
            f'<cc:B>{(i * 90) % 256}</cc:B></cc:ColorRGB>'
            f'</cc:DeviceColorValues></cc:Object>')
    specs = "".join(
        f'<cc:ColorSpecification Id="{c}_Measurement_spec"><cc:MeasurementSpec>'
        f'<cc:WavelengthRange StartWL="380" Increment="10"/>'
        f'</cc:MeasurementSpec></cc:ColorSpecification>' for c in conditions)
    sel = ("" if selected is None
           else f' SelectedMeasurementCondition="{selected}"')
    path.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<cc:CxF xmlns:cc="{_NS}">'
        f'<cc:FileInformation><cc:Creator>X-Rite - Prism</cc:Creator>'
        f'</cc:FileInformation><cc:Resources><cc:ObjectCollection>'
        f'{"".join(objs)}</cc:ObjectCollection><cc:ColorSpecificationCollection>'
        f'{specs}</cc:ColorSpecificationCollection></cc:Resources>'
        f'<cc:CustomResources><xrp:Prism xmlns:xrp="http://www.xrite.com/'
        f'products/prism" release="2.0"><xrp:CustomAttributes ColorSpace="RGB" '
        f'MeasurementDevice="i1Pro 3"{sel}/></xrp:Prism></cc:CustomResources>'
        f'</cc:CxF>', encoding="utf-8")
    return path


# ---- i1Profiler's number ---------------------------------------------------

@pytest.mark.parametrize("number, cond", [("0", "M0"), ("1", "M1"),
                                          ("2", "M2"), (" 2 ", "M2")])
def test_i1profilers_number_names_the_condition(number, cond):
    assert condition_from_label(number) == cond


@pytest.mark.parametrize("value", ["3", "-1", "7", "12", "1.5", "", None])
def test_any_other_value_names_nothing(value):
    assert condition_from_label(value) is None


@pytest.mark.parametrize("number, cond", [("0", "M0"), ("1", "M1"),
                                          ("2", "M2")])
def test_the_condition_chosen_in_i1profiler_is_preselected(tmp_path, number,
                                                            cond):
    """jctay's three saves of one measurement (all three conditions held)."""
    c = cxf_conditions(_native(tmp_path / "a.mxf", ("M0", "M1", "M2"),
                               number))
    assert c.selected == cond and c.preselect == cond and c.needs_choice
    line = M.cxf_condition_setting_line(c.selected_raw, c.selected,
                                        c.preselect)
    assert line == M.tr(M._COND_SETTING_KNOWN).format(condition=cond)
    assert "i1Profiler" in line and "another condition" in line
    assert read_condition(cxf_measurement_to_ti3(
        tmp_path / "a.mxf", tmp_path / "o.ti3")) == cond


def test_text_labels_keep_working(tmp_path):
    c = cxf_conditions(_native(tmp_path / "a.mxf", ("M0", "M1", "M2"),
                               "UV excluded [M2]"))
    assert c.selected == "M2" and c.preselect == "M2"


def test_an_unknown_number_falls_back_to_m1_and_says_so(tmp_path):
    c = cxf_conditions(_native(tmp_path / "a.mxf", ("M0", "M1", "M2"), "5"))
    assert c.selected is None and c.preselect == "M1"
    line = M.cxf_condition_setting_line(c.selected_raw, c.selected,
                                        c.preselect)
    assert "“5”" in line and "M1" in line


def test_a_chosen_condition_the_file_does_not_hold_falls_back(tmp_path):
    """i1Profiler says M2, the file holds M0 and M1: the current rule (M1),
    and the line says why."""
    c = cxf_conditions(_native(tmp_path / "a.mxf", ("M0", "M1"), "2"))
    assert c.selected == "M2" and c.preselect == "M1"
    line = M.cxf_condition_setting_line(c.selected_raw, c.selected,
                                        c.preselect)
    assert line == M.tr(M._COND_SETTING_ABSENT).format(selected="M2",
                                                       condition="M1")
    c = cxf_conditions(_native(tmp_path / "b.mxf", ("M0", "M2"), "1"))
    assert c.preselect == "M0"            # no M1 either: the first held


# ---- files that hold only some conditions (jctay's native_* files) --------

#: (conditions held, i1Profiler's number), as in his five files.
_NATIVE = [(("M0",), "0"), (("M1",), "1"), (("M2",), "2"),
           (("M0", "M1"), "0"), (("M1", "M2"), "1")]


@pytest.mark.parametrize("held, number", _NATIVE)
def test_every_combination_imports_under_each_condition_it_holds(
        tmp_path, held, number):
    src = _native(tmp_path / "n.mxf", held, number)
    c = cxf_conditions(src)
    assert c.available == held
    assert c.needs_choice == (len(held) > 1)
    assert c.preselect == {"0": "M0", "1": "M1", "2": "M2"}[number]
    for cond in ("M0", "M1", "M2"):
        out = tmp_path / f"{cond}.ti3"
        if cond not in held:
            with pytest.raises(ReferenceConvertError):
                cxf_measurement_to_ti3(src, out, condition=cond)
            continue
        cxf_measurement_to_ti3(src, out, condition=cond)
        assert read_condition(out) == cond
        text = out.read_text(encoding="utf-8")
        assert 'KEYWORD "MEASUREMENT_CONDITION"' in text
        assert f"NUMBER_OF_SETS {_N}" in text
        refused = fwa_refusal_for_file(out)
        # FWA only for M0 readings (the FWA gate, 4.3.23)
        assert (refused is None) == (cond == "M0"), (cond, refused)


@pytest.mark.parametrize("held, number", _NATIVE)
def test_the_window_asks_only_with_a_choice_and_offers_only_those(
        qapp, tmp_path, monkeypatch, held, number):
    import ui.dialogs.cxf_condition_dialog as ccd
    from PyQt6.QtWidgets import QRadioButton
    seen = []

    def _answer(dlg):
        radios = {r.objectName(): r for r in dlg.findChildren(QRadioButton)}
        seen.append(radios)
        return True
    monkeypatch.setattr(ccd, "_run", _answer)
    log = []
    got = ccd.choose_cxf_condition(None, _native(tmp_path / "n.mxf", held,
                                                 number), log=log.append)
    want = {"0": "M0", "1": "M1", "2": "M2"}[number]
    assert got == want
    if len(held) == 1:
        assert not seen, "a file with one condition asked anyway"
        assert log == [M.cxf_condition_log_line(want, held)]
        return
    assert len(seen) == 1
    radios = seen[0]
    assert set(radios) == {f"cxf_condition_{c}" for c in held}
    assert radios[f"cxf_condition_{want}"].isChecked()
    assert log == [M.cxf_condition_log_line(want, held)]


def test_imports_of_two_conditions_are_not_merged_one_condition_is(tmp_path):
    """The merge / average rule (4.3.23) sees what the import recorded."""
    m0 = cxf_measurement_to_ti3(_native(tmp_path / "a.mxf", ("M0",), "0"),
                                tmp_path / "a.ti3")
    m1 = cxf_measurement_to_ti3(_native(tmp_path / "b.mxf", ("M1",), "1"),
                                tmp_path / "b.ti3")
    m1b = cxf_measurement_to_ti3(
        _native(tmp_path / "c.mxf", ("M1", "M2"), "1"), tmp_path / "c.ti3")
    assert condition_check([m0, m1]).clash is not None
    ok = condition_check([m1, m1b])
    assert ok.clash is None and ok.common == "M1" and not ok.asks


def test_the_line_about_i1profilers_choice_stands_above_the_choices(
        qapp, tmp_path):
    """It says the condition "is selected below", so it comes first (on
    screen, 4.3.24: under the choices it pointed at nothing)."""
    from PyQt6.QtWidgets import QLabel, QRadioButton
    from ui.dialogs.cxf_condition_dialog import CxfConditionDialog
    conds = cxf_conditions(_native(tmp_path / "a.mxf", ("M1", "M2"), "1"))
    dlg = CxfConditionDialog(None, "a.mxf", conds)
    lay = dlg.layout()
    order = [lay.itemAt(i).widget() for i in range(lay.count())]
    line = dlg.findChild(QLabel, "cxf_condition_setting")
    first_radio = min(order.index(r) for r in dlg.findChildren(QRadioButton))
    assert order.index(line) < first_radio
    assert "below" in line.text()
    dlg.deleteLater()
