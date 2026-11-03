"""4.3.23: an i1Profiler CxF is imported under the measurement condition the
person chooses, keeps its spectra, names the condition and ArgyllCMS's name
for the instrument, and brightener compensation (FWA) is kept off M1 / M2
readings.

jctay (printerknowledge, 2026-11-03) converted the same .mxf with his own
tool and with ChromIQ and found 4.4 dE76 between them on average: ChromIQ had
taken the M2 readings without asking or saying so, and he compared with M1.
Basti, 2026-11-03: "ChromIQ offers a choice of condition." Every fixture
here is synthetic, with invented values.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M                    # noqa: E402
from workflow.fwa_gate import (                                      # noqa: E402
    drop_fwa, fwa_refusal, fwa_refusal_for_file, without_refused_fwa)
from workflow.measurement_condition import read_condition            # noqa: E402
from workflow.reference_convert import (                             # noqa: E402
    ReferenceConvertError, argyll_instrument_name, condition_from_label,
    convert_i1profiler_measurement, cxf_conditions, cxf_measurement_to_ti3,
    same_instrument)
from workflow.ti3_analysis import parse_ti3                          # noqa: E402

_NS = "http://colorexchangeformat.com/CxF3-core"


def _patches(n: int = 27):
    """n device colours on a 3x3x3 grid and a smooth invented spectrum each."""
    vals = (0, 128, 255)
    rgb = [(r, g, b) for r in vals for g in vals for b in vals][:n]
    lam = np.arange(36)

    def spectrum(r, g, b):
        base = 0.04 + 0.8 * (
            (r / 255) * np.exp(-((lam - 28) / 6.0) ** 2)
            + (g / 255) * np.exp(-((lam - 17) / 5.0) ** 2)
            + (b / 255) * np.exp(-((lam - 7) / 5.0) ** 2))
        return np.clip(base, 0.01, 0.95)
    return rgb, [spectrum(*c) for c in rgb]


#: How each condition's invented reading differs from M0's: M1 a little
#: brighter in the blue (a brightener glowing under D50), M2 without it.
_GLOW = {"M0": 1.00, "M1": 1.12, "M2": 0.90}


def _cxf(path: Path, *, conditions=("M0", "M1", "M2"), selected=None,
         device="i1Pro 3", start=380, step=10, bands=36) -> Path:
    rgb, spectra = _patches()
    objs = []
    for i, (r, g, b) in enumerate(rgb, 1):
        objs.append(
            f'<cc:Object ObjectType="Target" Name="Target{i}" Id="t{i}">'
            f'<cc:DeviceColorValues><cc:ColorRGB ColorSpecification="Unknown">'
            f'<cc:R>{r}</cc:R><cc:G>{g}</cc:G><cc:B>{b}</cc:B></cc:ColorRGB>'
            f'</cc:DeviceColorValues></cc:Object>')
    specs = []
    for c in conditions:
        for i, sp in enumerate(spectra, 1):
            v = sp[:bands].copy()
            v[:12] = v[:12] * _GLOW[c]          # the blue end glows, or not
            s = " ".join(f"{x:.6f}" for x in v)
            objs.append(
                f'<cc:Object ObjectType="{c}_Measurement" Name="{c}_Measurement{i}" '
                f'Id="{c}{i}"><cc:CreationDate>2026-11-02T06:27:39Z</cc:CreationDate>'
                f'<cc:ColorValues><cc:ReflectanceSpectrum StartWL="{start}" '
                f'ColorSpecification="{c}_spec">{s}</cc:ReflectanceSpectrum>'
                f'</cc:ColorValues></cc:Object>')
        specs.append(
            f'<cc:ColorSpecification Id="{c}_spec"><cc:MeasurementSpec>'
            f'<cc:WavelengthRange StartWL="{start}" Increment="{step}"/>'
            f'</cc:MeasurementSpec></cc:ColorSpecification>')
    sel = (f' SelectedMeasurementCondition="{selected}"'
           if selected is not None else "")
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<cc:CxF xmlns:cc="{_NS}">'
           f'<cc:Resources><cc:ObjectCollection>{"".join(objs)}'
           f'</cc:ObjectCollection><cc:ColorSpecificationCollection>'
           f'{"".join(specs)}</cc:ColorSpecificationCollection></cc:Resources>'
           f'<cc:CustomResources><xrp:Prism xmlns:xrp="http://www.xrite.com/products/prism">'
           f'<xrp:CustomAttributes MeasurementDevice="{device}"{sel}/>'
           f'</xrp:Prism></cc:CustomResources></cc:CxF>')
    path.write_text(xml, encoding="utf-8")
    return path


# ---- which conditions, and which is offered first ------------------------

def test_a_number_is_never_taken_for_a_condition_so_m1_is_offered(tmp_path):
    """jctay's file says SelectedMeasurementCondition="0": probably M0, not
    proved, so it is reported and M1 is preselected (Basti, 2026-11-03)."""
    c = cxf_conditions(_cxf(tmp_path / "a.mxf", selected="0"))
    assert c.available == ("M0", "M1", "M2")
    assert c.selected_raw == "0" and c.selected is None
    assert c.preselect == "M1" and c.needs_choice


def test_a_text_label_names_its_condition_with_certainty(tmp_path):
    """X-Rite's i1iSis sample writes "UV excluded [M2]"."""
    c = cxf_conditions(_cxf(tmp_path / "a.mxf", selected="UV excluded [M2]"))
    assert c.selected == "M2" and c.preselect == "M2"
    assert condition_from_label("M0") == "M0"
    assert condition_from_label("Daylight [M1]") == "M1"
    for unsure in ("0", "1", "2", "", None, "M0 or M2", "D50"):
        assert condition_from_label(unsure) is None, unsure


def test_a_file_with_one_condition_needs_no_choice(tmp_path):
    c = cxf_conditions(_cxf(tmp_path / "a.mxf", conditions=("M2",)))
    assert c.available == ("M2",) and not c.needs_choice
    assert c.preselect == "M2"


def test_m1_missing_falls_back_to_the_first_condition_held(tmp_path):
    c = cxf_conditions(_cxf(tmp_path / "a.mxf", conditions=("M0", "M2")))
    assert c.preselect == "M0"


# ---- the conversion ---------------------------------------------------------

@pytest.mark.parametrize("cond", ["M0", "M1", "M2"])
def test_each_condition_converts_its_own_readings_and_says_which(tmp_path,
                                                                 cond):
    """Before 4.3.23 every one of these was the M2 readings, with no
    condition in the file and no spectra."""
    from workflow.profile_engine.spectral import spectra_to_xyz
    src = _cxf(tmp_path / "a.mxf")
    out = cxf_measurement_to_ti3(src, tmp_path / f"{cond}.ti3", condition=cond)
    d = parse_ti3(out)
    assert d.keywords["MEASUREMENT_CONDITION"] == cond
    assert 'KEYWORD "MEASUREMENT_CONDITION"' in out.read_text(encoding="utf-8")
    assert d.has_spectral and len(d.wavelengths) == 36
    _rgb, spectra = _patches()
    want = np.array([s.copy() for s in spectra])
    want[:, :12] *= _GLOW[cond]
    assert np.allclose(np.asarray(d.spectral), want * 100, atol=1e-4)
    xyz = spectra_to_xyz(want, 380 + 10 * np.arange(36), illuminant="D50")
    assert np.allclose(np.asarray(d.xyz), xyz, atol=1e-3)


def test_the_conditions_give_different_numbers(tmp_path):
    src = _cxf(tmp_path / "a.mxf")
    ys = {c: np.asarray(parse_ti3(cxf_measurement_to_ti3(
        src, tmp_path / f"{c}.ti3", condition=c)).xyz)[:, 2].sum()
        for c in ("M0", "M1", "M2")}
    assert ys["M1"] > ys["M0"] > ys["M2"]


def test_no_condition_named_takes_the_preselection_never_m2_in_silence(
        tmp_path):
    out = cxf_measurement_to_ti3(_cxf(tmp_path / "a.mxf", selected="0"),
                                 tmp_path / "o.ti3")
    assert read_condition(out) == "M1"


def test_a_condition_the_file_does_not_hold_is_refused(tmp_path):
    with pytest.raises(ReferenceConvertError):
        cxf_measurement_to_ti3(_cxf(tmp_path / "a.mxf", conditions=("M2",)),
                               tmp_path / "o.ti3", condition="M0")


def test_the_wavelengths_are_the_files_own(tmp_path):
    """Start and step from the file (StartWL, WavelengthRange Increment),
    never 380 / 10 nm assumed: here 400 nm in 20 nm steps."""
    src = _cxf(tmp_path / "a.mxf", start=400, step=20, bands=16)
    d = parse_ti3(cxf_measurement_to_ti3(src, tmp_path / "o.ti3",
                                         condition="M1"))
    assert list(np.asarray(d.wavelengths)) == [400 + 20 * k for k in range(16)]
    text = (tmp_path / "o.ti3").read_text(encoding="utf-8")
    assert 'SPECTRAL_BANDS "16"' in text
    assert 'SPECTRAL_START_NM "400.000000"' in text
    assert 'SPECTRAL_END_NM "700.000000"' in text
    assert "SPEC_400 SPEC_420" in text and "SPEC_700" in text


def test_the_dispatcher_passes_the_condition_on(tmp_path):
    out = convert_i1profiler_measurement(_cxf(tmp_path / "a.mxf"),
                                         "/nonexistent", tmp_path / "d",
                                         condition="M2")
    assert read_condition(out) == "M2"


# ---- the instrument's name ----------------------------------------------------

def test_argyllcms_names_for_i1profilers_instruments():
    assert argyll_instrument_name("i1Pro 3") == "X-Rite i1 Pro 3"
    assert argyll_instrument_name("i1Pro 3 Plus") == "X-Rite i1 Pro 3"
    assert argyll_instrument_name("i1Pro 2") == "X-Rite i1 Pro 2"
    assert argyll_instrument_name("i1Pro") == "GretagMacbeth i1 Pro"
    assert argyll_instrument_name("i1iO 2") == "X-Rite i1 Pro 2"
    assert argyll_instrument_name("i1iO") == "GretagMacbeth i1 Pro"
    # ArgyllCMS's own names and instruments it does not know stay as they are
    for keep in ("X-Rite i1 Pro 3", "GretagMacbeth i1 Pro", "i1iSis",
                 "X-Rite ColorMunki", "i1Profiler (unspecified)"):
        assert argyll_instrument_name(keep) == keep
    assert same_instrument("i1Pro 3", "X-Rite i1 Pro 3")
    assert not same_instrument("i1Pro 2", "X-Rite i1 Pro 3")


def test_the_import_writes_argylls_name_and_keeps_i1profilers(tmp_path):
    out = cxf_measurement_to_ti3(_cxf(tmp_path / "a.mxf"), tmp_path / "o.ti3",
                                 condition="M0")
    kw = parse_ti3(out).keywords
    assert kw["TARGET_INSTRUMENT"] == "X-Rite i1 Pro 3"
    assert kw["CHROMIQ_I1P_INSTRUMENT"] == "i1Pro 3"
    assert 'KEYWORD "CHROMIQ_I1P_INSTRUMENT"' in out.read_text(encoding="utf-8")


def test_old_and_new_names_read_the_same_everywhere():
    """An import made by 4.3.22 ("i1Pro 3") still works with every reader."""
    from ui.ti2_loader import instrument_family, instrument_label, is_i1pro
    for name in ("i1Pro 3", "X-Rite i1 Pro 3", "i1Pro 2", "X-Rite i1 Pro 2",
                 "GretagMacbeth i1 Pro"):
        assert is_i1pro(name), name
        assert instrument_label(name) == "i1Pro / i1Pro2 / i1Pro3(+)"
        assert instrument_family(name) == "i1pro"
    from workflow.profile_engine.fwa import instrument_supports_fwa
    assert instrument_supports_fwa("X-Rite i1 Pro 3")


def test_the_report_does_not_call_old_and_new_names_two_instruments():
    from workflow.measurement_report import report_scope
    runs = [{"chart": "A", "created": "2026-11-01", "instrument": "i1Pro 3"},
            {"chart": "A", "created": "2026-11-02",
             "instrument": "X-Rite i1 Pro 3"},
            {"chart": "A", "created": "2026-11-03",
             "instrument": "X-Rite i1 Pro 3"}]
    scope = report_scope(runs)
    assert not [w for w in scope["warnings"] if w["kind"] == "instrument"]
    runs.append({"chart": "A", "created": "2026-11-04",
                 "instrument": "X-Rite ColorMunki"})
    assert [w for w in report_scope(runs)["warnings"]
            if w["kind"] == "instrument"]


# ---- the consumers of a converted file with spectra ---------------------------

def test_the_spectral_options_are_offered_for_an_import_now(tmp_path):
    from ui.ti2_loader import has_spectral_data, spectral_options_unavailable
    out = cxf_measurement_to_ti3(_cxf(tmp_path / "a.mxf"), tmp_path / "o.ti3",
                                 condition="M1")
    assert has_spectral_data(out)
    assert not spectral_options_unavailable("X-Rite i1 Pro 3",
                                            has_spectral_data(out))


def test_an_import_merges_with_a_chartread_measurement_of_its_layout(
        tmp_path):
    """Same columns as chartread now; only two NAMED, different conditions
    are refused."""
    from workflow.ti3_merge import merge_refusal
    src = _cxf(tmp_path / "a.mxf")
    m1 = cxf_measurement_to_ti3(src, tmp_path / "m1.ti3", condition="M1")
    m2 = cxf_measurement_to_ti3(src, tmp_path / "m2.ti3", condition="M2")
    chartread_like = tmp_path / "cr.ti3"
    chartread_like.write_text(
        re.sub(r'(KEYWORD "MEASUREMENT_CONDITION"\n)?MEASUREMENT_CONDITION "M1"\n',
               "", m1.read_text(encoding="utf-8")), encoding="utf-8")
    assert read_condition(chartread_like) is None
    assert merge_refusal(m1, chartread_like) is None
    refusal = merge_refusal(m1, m2)
    assert refusal and "M2" in refusal and "M1" in refusal


def test_the_turned_reorder_keeps_every_spectrum(tmp_path):
    """The turned chart's reorder rewrites rows by their columns; the spectra
    travel with their reading."""
    from tests.test_i1profiler_turned_doors import _well_filed  # noqa: F401
    from tests.test_i1profiler_turned_grid_check import _mxf
    from tests.test_i1profiler_turned_export import _chart
    from core.file_manager import exports_subdir
    from workflow import i1profiler_turned as T
    ti2 = _chart(tmp_path / "proj", "Proj", 350)
    T.write_turned_export(ti2, exports_subdir(ti2.parent), "Proj")
    files = T.TurnedFiles(exports_subdir(ti2.parent), "Proj")
    plan = T.plan_for(ti2)
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "t.mxf", columns=plan.columns)
    ti3 = cxf_measurement_to_ti3(mxf, tmp_path / "t.ti3", condition="M0")
    before = parse_ti3(ti3)
    by_dev = {tuple(np.round(r, 3)): tuple(np.round(s, 4))
              for r, s in zip(before.rgb, before.spectral)}
    assert T.reorder_turned_measurement(ti3, ti2) == len(plan.order)
    after = parse_ti3(ti3)
    assert after.has_spectral and len(after.wavelengths) == 36
    for r, s in zip(after.rgb, after.spectral):
        assert by_dev[tuple(np.round(r, 3))] == tuple(np.round(s, 4))


# ---- FWA: only M0 readings ------------------------------------------------------

def test_fwa_is_refused_for_m1_and_m2_only():
    i1 = "X-Rite i1 Pro 3"
    assert fwa_refusal(i1, condition=None) is None
    assert fwa_refusal(i1, condition="M0") is None
    for cond in ("M1", "m2"):
        refusal = fwa_refusal(i1, condition=cond)
        assert refusal.kind == "condition"
        assert refusal.condition == cond.upper()


def _params(ti3, **kw):
    from workflow.profile_builder import ProfileParams
    return ProfileParams(ti3_path=ti3, **kw)


@pytest.mark.parametrize("cond,has_f", [("M0", True), ("M1", False),
                                        ("M2", False)])
def test_colprof_never_gets_f_for_m1_or_m2(tmp_path, cond, has_f):
    from workflow.profile_builder import ProfileBuilder
    ti3 = cxf_measurement_to_ti3(_cxf(tmp_path / "a.mxf"),
                                 tmp_path / "o.ti3", condition=cond)
    args = ProfileBuilder(None)._build_args(
        _params(ti3, fwa_enabled=True, fwa_illum="D50",
                extra_args="-f -qm"))
    assert any(a.startswith("-f") for a in args) is has_f, args


def test_the_build_floor_drops_f_and_says_so(tmp_path):
    """A preset or saved setting can tick FWA; the build takes it out, with a
    line in the log, and never crashes."""
    from workflow.profile_builder import ProfileBuilder
    ti3 = cxf_measurement_to_ti3(_cxf(tmp_path / "a.mxf"),
                                 tmp_path / "o.ti3", condition="M1")
    ran = {}

    class _Runner:
        def run(self, tool, args, cwd, on_line, on_finish):
            ran["args"] = args
    lines = []
    ProfileBuilder(_Runner()).build(_params(ti3, fwa_enabled=True),
                                    lines.append, lambda c: None)
    assert not any(a.startswith("-f") for a in ran["args"])
    assert any("FWA" in ln and "M1" in ln for ln in lines), lines


def test_the_check_floor_drops_f_too(tmp_path):
    from workflow.profcheck_runner import ProfcheckParams, ProfcheckRunner
    ti3 = cxf_measurement_to_ti3(_cxf(tmp_path / "a.mxf"),
                                 tmp_path / "o.ti3", condition="M2")
    icc = tmp_path / "o.icc"
    icc.write_bytes(b"x")
    ran = {}

    class _Runner:
        def run(self, tool, args, cwd, on_line, on_finish):
            ran["args"] = args
    lines = []
    ProfcheckRunner(_Runner()).run(
        ProfcheckParams(ti3_path=ti3, icc_path=icc, fwa_enabled=True),
        lines.append, lambda c: None)
    assert not any(a.startswith("-f") for a in ran["args"])
    assert any("M2" in ln for ln in lines)


def test_remove_fwa_takes_typed_f_out_and_keeps_the_rest():
    class P:
        fwa_enabled = True
        extra_args = "-qh -fD65 -v"
    p = P()
    assert drop_fwa(p)
    assert not p.fwa_enabled and p.extra_args == "-qh -v"


def test_a_file_without_a_condition_is_judged_as_before(tmp_path):
    ti3 = tmp_path / "cr.ti3"
    ti3.write_text("CTI3\nTARGET_INSTRUMENT \"X-Rite i1 Pro 3\"\nBEGIN_DATA\n"
                   "END_DATA\n", encoding="utf-8")
    assert fwa_refusal_for_file(ti3) is None
    p = _params(ti3, fwa_enabled=True)
    same, dropped = without_refused_fwa(p)
    assert same is p and dropped is None


def _settings(tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


def test_build_profile_greys_fwa_for_m1_and_says_why(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_profile import TabProfile
    s = _settings(tmp_path)
    tab = TabProfile(ArgyllRunner(s), s)
    tab._fwa_check.setChecked(True)
    tab._m_fwa_check.setChecked(True)
    src = _cxf(tmp_path / "a.mxf")
    m1 = cxf_measurement_to_ti3(src, tmp_path / "m1.ti3", condition="M1")
    tab._ti3_path = m1
    tab._detect_instrument(m1)
    for w in (tab._fwa_check, tab._fwa_illum_combo, tab._m_fwa_check,
              tab._m_fwa_illum_combo):
        assert not w.isEnabled()
        assert "M1" in w.toolTip() and "M0" in w.toolTip()
    assert tab._fwa_check.isChecked(), "a setting is not changed by a load"
    params = tab._collect_params()
    assert not params.fwa_enabled
    assert tab._fwa_dropped_by_collect.condition == "M1"
    # an M0 measurement gives it back, with its own tooltip
    m0 = cxf_measurement_to_ti3(src, tmp_path / "m0.ti3", condition="M0")
    tab._ti3_path = m0
    tab._detect_instrument(m0)
    assert tab._fwa_check.isEnabled() and tab._fwa_illum_combo.isEnabled()
    assert "M1" not in tab._fwa_check.toolTip()
    assert tab._collect_params().fwa_enabled
    tab.deleteLater()


def test_check_and_refine_greys_fwa_for_m2(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_check_refine import TabCheckRefine
    s = _settings(tmp_path)
    tab = TabCheckRefine(ArgyllRunner(s), s)
    tab._fwa_cb.setChecked(True)
    m2 = cxf_measurement_to_ti3(_cxf(tmp_path / "a.mxf"),
                                tmp_path / "m2.ti3", condition="M2")
    tab._ti3_path = m2
    tab._detect_instrument(m2)
    assert not tab._fwa_cb.isEnabled() and not tab._fwa_combo.isEnabled()
    assert "M2" in tab._fwa_cb.toolTip()
    assert not tab._collect_params().fwa_enabled
    tab._detect_instrument(None)
    assert tab._fwa_cb.isEnabled() and tab._fwa_combo.isEnabled()
    tab.deleteLater()


# ---- the window ----------------------------------------------------------------

def test_the_window_offers_the_files_conditions_preselected(qapp, tmp_path):
    from ui.dialogs.cxf_condition_dialog import CxfConditionDialog
    conds = cxf_conditions(_cxf(tmp_path / "a.mxf", selected="0"))
    dlg = CxfConditionDialog(None, "a.mxf", conds)
    from PyQt6.QtWidgets import QLabel, QRadioButton
    radios = {r.objectName(): r for r in dlg.findChildren(QRadioButton)}
    assert set(radios) == {"cxf_condition_M0", "cxf_condition_M1",
                           "cxf_condition_M2"}
    assert radios["cxf_condition_M1"].isChecked() and dlg.condition() == "M1"
    text = "\n".join(lb.text() for lb in dlg.findChildren(QLabel))
    assert "a.mxf" in text and "M0, M1 and M2" in text
    assert "“0”" in text            # i1Profiler's setting, named
    assert "only works with M0 readings" in text
    assert "ISO 13655" in text
    dlg.select("M0")
    assert dlg.condition() == "M0"
    dlg.deleteLater()


def test_choose_asks_only_when_there_is_a_choice(qapp, tmp_path, monkeypatch):
    import ui.dialogs.cxf_condition_dialog as ccd
    from ui.dialogs.cxf_condition_dialog import choose_cxf_condition
    asked = []

    def _answer_m2(dlg):
        asked.append(dlg)
        dlg.select("M2")
        return True
    monkeypatch.setattr(ccd, "_run", _answer_m2)
    log = []
    assert choose_cxf_condition(None, _cxf(tmp_path / "a.mxf"),
                                log=log.append) == "M2"
    assert len(asked) == 1 and "M2" in log[-1] and "M0 and M1" in log[-1]
    one = _cxf(tmp_path / "one.mxf", conditions=("M0",))
    assert choose_cxf_condition(None, one, log=log.append) == "M0"
    assert len(asked) == 1, "a file with one condition asked anyway"
    assert log[-1] == M.cxf_condition_log_line("M0", ("M0",))
    assert "only one" in log[-1]
    # Cancel imports nothing and says so
    monkeypatch.setattr(ccd, "_run", lambda dlg: False)
    assert choose_cxf_condition(None, _cxf(tmp_path / "b.mxf"),
                                log=log.append) is None
    assert log[-1] == M.cxf_condition_cancelled_line()
    # not a CxF: nothing to choose
    assert choose_cxf_condition(None, tmp_path / "x.txt") == ""


def test_the_toolbox_converter_asks_and_writes_the_choice(qapp, tmp_path,
                                                          monkeypatch):
    import ui.dialogs.cxf_condition_dialog as ccd
    from core.argyll_runner import ArgyllRunner
    from ui.dialogs.tools_dialogs import I1ProfilerToTi3Dialog
    s = _settings(tmp_path)
    dlg = I1ProfilerToTi3Dialog(ArgyllRunner(s), s)

    def _m0(d):
        d.select("M0")
        return True
    monkeypatch.setattr(ccd, "_run", _m0)
    dlg._txt = _cxf(tmp_path / "a.mxf")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(type(dlg._output), "directory",
                        property(lambda self: out_dir))
    monkeypatch.setattr(type(dlg._output), "name",
                        property(lambda self: "conv"))
    finished = []
    monkeypatch.setattr(dlg, "_finish", finished.append)
    dlg._execute()
    assert finished == [True]
    assert read_condition(out_dir / "conv.ti3") == "M0"
    assert "Measurement condition: M0" in dlg._log.toPlainText()
    dlg.deleteLater()


# ---- the info window -------------------------------------------------------------

def test_the_info_window_shows_when_it_was_measured_and_the_condition(
        qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    s = _settings(tmp_path)
    out = cxf_measurement_to_ti3(_cxf(tmp_path / "a.mxf"), tmp_path / "o.ti3",
                                 condition="M1")
    assert "CREATED" not in parse_ti3(out).keywords
    dlg = Ti3InfoDialog(ArgyllRunner(s), s)
    dlg.load_measurement(out)
    report = "\n".join(dlg._report)
    assert "2026-11-02" in report, report          # from CHROMIQ_MEASURED
    assert "M1 (daylight with UV, D50)" in report
    assert "X-Rite i1 Pro 3 (in i1Profiler: i1Pro 3)" in report
    dlg.deleteLater()


# ---- the -F tooltip ----------------------------------------------------------------

def test_the_filter_tooltip_no_longer_claims_a_d50_default():
    import inspect
    from ui.tabs import tab_measure
    src = inspect.getsource(tab_measure)
    assert "The app defaults to D50 (M1)" not in src
    assert "ChromIQ does not pass -F at all" in src


# ---- ArgyllCMS itself reads the result ------------------------------------------

def _argyll(tool):
    return shutil.which(tool)


@pytest.mark.skipif(not _argyll("spec2cie"), reason="ArgyllCMS not installed")
def test_argyllcms_applies_fwa_to_an_m0_import(tmp_path):
    """With i1Profiler's name ("i1Pro 3") spec2cie -f stopped with
    "Unrecognised target instrument" (jctay's file, 2026-11-03)."""
    out = cxf_measurement_to_ti3(_cxf(tmp_path / "a.mxf"), tmp_path / "o.ti3",
                                 condition="M0")
    r = subprocess.run([_argyll("spec2cie"), "-f", "-i", "D50", str(out),
                        str(tmp_path / "f.ti3")], capture_output=True,
                       text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    old = tmp_path / "old.ti3"
    old.write_text(out.read_text(encoding="utf-8").replace(
        'TARGET_INSTRUMENT "X-Rite i1 Pro 3"', 'TARGET_INSTRUMENT "i1Pro 3"'),
        encoding="utf-8")
    r = subprocess.run([_argyll("spec2cie"), "-f", "-i", "D50", str(old),
                        str(tmp_path / "g.ti3")], capture_output=True,
                       text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert r.returncode != 0 and "nrecognised target instrument" in (
        r.stdout + r.stderr)


@pytest.mark.skipif(not _argyll("colprof"), reason="ArgyllCMS not installed")
def test_a_spectral_import_builds_a_profile(tmp_path):
    """The import with spectra, through ProfileBuilder's own arguments, makes
    a profile in colprof (M1: no -f)."""
    from workflow.profile_builder import ProfileBuilder
    work = tmp_path / "b"
    work.mkdir()
    ti3 = cxf_measurement_to_ti3(_cxf(tmp_path / "a.mxf"), work / "P.ti3",
                                 condition="M1")
    args = ProfileBuilder(None)._build_args(
        _params(ti3, quality="l", fwa_enabled=True))
    assert not any(a.startswith("-f") for a in args)
    r = subprocess.run([_argyll("colprof"), *args], cwd=work,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=600)
    assert r.returncode == 0, (r.stdout + r.stderr)[-2000:]
    assert any(p.suffix in (".icc", ".icm") for p in work.iterdir())


# ---- through the doors: the chosen readings are filed into a run ---------------

from tests.test_i1profiler_turned_doors import house, turned_source  # noqa: E402,F401


def _three_conditions(m0_mxf: Path, out: Path) -> Path:
    """*m0_mxf* (M0 readings only) with M1 and M2 copies beside them, every
    M2 value 0.9 times M0's and every M1 value 1.05 times (invented)."""
    text = m0_mxf.read_text(encoding="utf-8")
    m0 = re.findall(r'(<cc:Object ObjectType="M0_Measurement".*?</cc:Object>)',
                    text, flags=re.S)
    extra = []
    for cond, k in (("M1", 1.05), ("M2", 0.9)):
        for o in m0:
            o = o.replace("M0_Measurement", f"{cond}_Measurement")
            o = re.sub(r'Id="([^"]+)"', rf'Id="\1{cond}"', o)
            o = re.sub(r'(<cc:ReflectanceSpectrum[^>]*>)([^<]*)(<)',
                       lambda m: m.group(1) + " ".join(
                           f"{float(v) * k:.8f}" for v in m.group(2).split())
                       + m.group(3), o)
            extra.append(o)
    out.write_text(text.replace("</cc:ObjectCollection>",
                                "".join(extra) + "</cc:ObjectCollection>"),
                   encoding="utf-8")
    return out


def _pick(monkeypatch, cond, asked):
    import ui.dialogs.cxf_condition_dialog as ccd

    def _answer(dlg):
        asked.append(dlg.condition())        # what was preselected
        dlg.select(cond)
        return True
    monkeypatch.setattr(ccd, "_run", _answer)


def test_build_profile_files_the_chosen_condition_into_a_run(house,
                                                             monkeypatch):
    from tests.test_i1profiler_turned_doors import _answer, _the_only_new_run
    win, work, proj, run, outside, (_s, mxf, _t, truth) = house
    seen = _answer(monkeypatch, run_id="run1")
    asked = []
    _pick(monkeypatch, "M2", asked)
    import ui.tabs.tab_profile as tp
    loose = _three_conditions(mxf, outside / "three.mxf")
    before_bytes = loose.read_bytes()
    before = {p.name for p in proj.runs_root.iterdir() if p.is_dir()}
    monkeypatch.setattr(tp, "open_file_dialog", lambda *a, **k: str(loose))
    win._tab_profile._on_load_ti3()
    assert asked == ["M1"], "asked once, M1 preselected"
    assert seen["refused"] == [], seen["refused"]
    new_dir = _the_only_new_run(proj.root, before)
    filed = new_dir / "Turn.ti3"
    d = parse_ti3(filed)
    assert d.keywords["MEASUREMENT_CONDITION"] == "M2"
    assert d.keywords["TARGET_INSTRUMENT"] == "i1Profiler (unspecified)"
    assert d.has_spectral
    got = {sid: np.asarray(x) for sid, x in zip(d.sample_ids, d.xyz)}
    for sid, xyz in truth.items():
        assert np.allclose(got[sid], 0.9 * np.asarray(xyz), atol=2e-3), sid
    assert loose.read_bytes() == before_bytes


def test_build_profile_cancel_imports_nothing(house, monkeypatch):
    from tests.test_i1profiler_turned_doors import _answer
    import ui.dialogs.cxf_condition_dialog as ccd
    win, work, proj, run, outside, (_s, mxf, _t, _truth) = house
    _answer(monkeypatch, run_id="run1")
    monkeypatch.setattr(ccd, "_run", lambda dlg: False)
    import ui.tabs.tab_profile as tp
    loose = _three_conditions(mxf, outside / "three.mxf")
    before = {p.name for p in proj.runs_root.iterdir() if p.is_dir()}
    monkeypatch.setattr(tp, "open_file_dialog", lambda *a, **k: str(loose))
    win._tab_profile._on_load_ti3()
    after = {p.name for p in proj.runs_root.iterdir() if p.is_dir()}
    assert after == before
    assert M.cxf_condition_cancelled_line() in \
        win._tab_profile._log.toPlainText()


def test_the_measure_tab_files_the_chosen_condition(qapp, tmp_path,
                                                    turned_source,
                                                    monkeypatch):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.measurement_target import RUN_TYPE_PROFILING
    from core.settings import AppSettings
    from tests.test_i1profiler_turned_doors import (
        _answer, _project, _the_only_new_run)
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_measure import TabMeasure
    src_ti2, mxf, _t, truth = turned_source
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    work = tmp_path / "work"
    work.mkdir()
    s.set("custom_output_path", str(work))
    proj, run = _project(work, "M", src_ti2, with_measurement=True)
    fm = FileManager(s)
    fm.set_target_name("M")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)
    seen = _answer(monkeypatch, project="M")
    asked = []
    _pick(monkeypatch, "M0", asked)
    monkeypatch.setattr(tab, "_show_import_done_profiling", lambda *a: None)
    monkeypatch.setattr(tab, "_say_on_screen",
                        lambda t, b: seen["info"].append((t, b)))
    monkeypatch.setattr(tab, "_ask_how_printed", lambda *a: None)
    loose = _three_conditions(mxf, tmp_path / "three.mxf")
    before = {p.name for p in proj.runs_root.iterdir() if p.is_dir()}
    tab._import_into_profiling_run(ctl, fm.project().run("run1"), loose)
    assert asked == ["M1"]
    assert seen["refused"] == [], seen
    new_dir = _the_only_new_run(proj.root, before)
    d = parse_ti3(new_dir / "M.ti3")
    assert d.keywords["MEASUREMENT_CONDITION"] == "M0" and d.has_spectral
    got = {sid: tuple(np.round(x, 3)) for sid, x in zip(d.sample_ids, d.xyz)}
    assert got == truth
    assert "Measurement condition: M0" in tab._log.toPlainText()
    tab.deleteLater()
