"""A CMYK (or multi-ink) measurement is imported into a CMYK run (beta 7).

THE REPORT (forum, ajaytanna, 2026-10-03, CMYK + CR30). Measure ->
Import measurement refused his valid CMYK `.ti3` with "No device RGB columns,
only RGB charts are supported". Basti, the same day: *"yes, allow importing
cmyk into a cmyk run"*, and: there are several import paths.

WHAT CHANGED, AND WHAT DID NOT.

* `parse_ti3` still refuses every non-RGB file and `Ti3Data.has_device` still
  means "has RGB device values". Some thirty readers rely on that refusal; and
  had the parser returned a CMYK file with `rgb` empty, `has_device` would call
  it device-less and `assess` would send it down the §I.11 NAME pairing and
  write the chart's device values over its own. Both are pinned below.
* `measurement_import.assess` has its own non-RGB branch, built from the
  N-channel readers: the inks must be the chart's, the count rules are §I.10 /
  §I.12, and identity is per SAMPLE_ID through `device_values_differ` at
  `PATCH_IDENTITY_TOL`. Nothing in it is CMYK-specific, so multi-ink works the
  same way.
* Every door goes through `assess`: the Measure tab's IMPORT module (both run
  types, `TabMeasure._import_verdict`), Build Profile's "Load measurement data"
  (`measurement_filing.file_into_project` / `make_new_project_and_file`), and
  the i1Profiler CxF converter, which now writes CMYK as well as RGB.

The four cases on each path: CMYK into a CMYK run is filed; CMYK of another
chart is refused; RGB into a CMYK run is refused; CMYK into an RGB run is
refused.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measurement_import import assess                   # noqa: E402
from workflow.ti3_analysis import (Ti3ParseError, device_space_of,  # noqa: E402
                                   is_non_rgb_measurement, non_rgb_note,
                                   parse_ti3)

N = 24
INKS = {"CMYK": "CMYK_C CMYK_M CMYK_Y CMYK_K",
        "CMYKOG": "CMYKOG_C CMYKOG_M CMYKOG_Y CMYKOG_K CMYKOG_O CMYKOG_G",
        "iRGB": "RGB_R RGB_G RGB_B"}


def _dev(i: int, n_ch: int, salt: int = 0) -> "list[float]":
    return [float((i * (3 + c) + 7 * c + salt) % 101) for c in range(n_ch)]


def _chart(path: Path, rep: str = "CMYK", n: int = N) -> Path:
    """A `.ti2` of *rep* with its `.ti1` beside it."""
    f = INKS[rep]
    k = len(f.split())
    rows = [f'{i + 1} "A{i + 1}" ' + " ".join(f"{v:.1f}" for v in _dev(i, k))
            + " 40.0 42.0 44.0" for i in range(n)]
    path.write_text(
        'CTI2\n\nDESCRIPTOR "x"\nORIGINATOR "Argyll printtarg"\n'
        f'COLOR_REP "{rep}"\n\nNUMBER_OF_FIELDS {k + 5}\n'
        f"BEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC {f} XYZ_X XYZ_Y XYZ_Z\n"
        f"END_DATA_FORMAT\n\nNUMBER_OF_SETS {n}\nBEGIN_DATA\n"
        + "\n".join(rows) + "\nEND_DATA\n", encoding="utf-8")
    ti1_rows = [f"{i + 1} " + " ".join(f"{v:.1f}" for v in _dev(i, k))
                for i in range(n)]
    path.with_suffix(".ti1").write_text(
        f'CTI1\n\nCOLOR_REP "{rep}"\n\nNUMBER_OF_FIELDS {k + 1}\n'
        f"BEGIN_DATA_FORMAT\nSAMPLE_ID {f}\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n" + "\n".join(ti1_rows)
        + "\nEND_DATA\n", encoding="utf-8")
    return path


def _measurement(path: Path, rep: str = "CMYK", n: int = N, *, salt: int = 0,
                 xyz: bool = True) -> Path:
    """What chartread writes for that chart (salt != 0: another chart's)."""
    f = INKS[rep]
    k = len(f.split())
    cols = f"SAMPLE_ID SAMPLE_LOC {f}" + (" XYZ_X XYZ_Y XYZ_Z" if xyz else "")
    rows = [f'{i + 1} "A{i + 1}" ' + " ".join(
        f"{v:.1f}" for v in _dev(i, k, salt))
        + (f" {20 + i}.0 {21 + i}.0 {22 + i}.0" if xyz else "")
        for i in range(n)]
    path.write_text(
        'CTI3\n\nDESCRIPTOR "x"\nORIGINATOR "Argyll chartread"\n'
        f'DEVICE_CLASS "OUTPUT"\nCOLOR_REP "{rep}_XYZ"\n\n'
        f"NUMBER_OF_FIELDS {len(cols.split())}\nBEGIN_DATA_FORMAT\n{cols}\n"
        f"END_DATA_FORMAT\n\nNUMBER_OF_SETS {n}\nBEGIN_DATA\n"
        + "\n".join(rows) + "\nEND_DATA\n", encoding="utf-8")
    return path


# --- 0. what must not move -----------------------------------------------
def test_parse_ti3_still_refuses_a_cmyk_file(tmp_path):
    with pytest.raises(Ti3ParseError, match="only RGB charts"):
        parse_ti3(_measurement(tmp_path / "m.ti3"))


def test_has_device_still_means_rgb_device_values(tmp_path):
    rgb = parse_ti3(_measurement(tmp_path / "rgb.ti3", "iRGB"))
    assert rgb.has_device
    p = tmp_path / "bare.ti3"
    p.write_text('CTI3\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n'
                 'SAMPLE_ID XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n'
                 'NUMBER_OF_SETS 1\nBEGIN_DATA\n1 1 2 3\nEND_DATA\n', encoding="utf-8")
    assert not parse_ti3(p).has_device


def test_the_device_space_reader(tmp_path):
    assert device_space_of(_measurement(tmp_path / "a.ti3")) == "CMYK"
    assert device_space_of(_measurement(tmp_path / "b.ti3", "iRGB")) == "RGB"
    assert device_space_of(_chart(tmp_path / "c.ti2", "CMYKOG")) == "CMYKOG"
    assert device_space_of(tmp_path / "missing.ti3") is None
    assert is_non_rgb_measurement(tmp_path / "a.ti3")
    assert not is_non_rgb_measurement(tmp_path / "b.ti3")


# --- 1. the rule ------------------------------------------------------------
@pytest.mark.parametrize("rep", ["CMYK", "CMYKOG"])
def test_a_measurement_of_this_chart_is_filed(tmp_path, rep):
    chart = _chart(tmp_path / "run.ti2", rep)
    v = assess(_measurement(tmp_path / "m.ti3", rep), chart)
    assert v.ok, v.reason
    assert not v.partial and not v.device_from_chart
    assert v.n_measured == N and v.n_chart == N


def test_a_cmyk_measurement_of_another_chart_is_refused(tmp_path):
    """Same count, same inks, other device values: identity, per SAMPLE_ID."""
    chart = _chart(tmp_path / "run.ti2")
    v = assess(_measurement(tmp_path / "m.ti3", salt=13), chart)
    assert not v.ok
    assert "device values do not agree" in v.reason


def test_an_rgb_measurement_into_a_cmyk_run_is_refused(tmp_path):
    chart = _chart(tmp_path / "run.ti2", "CMYK")
    v = assess(_measurement(tmp_path / "m.ti3", "iRGB"), chart)
    assert not v.ok
    assert "measurement is RGB" in v.reason and "CMYK" in v.reason


def test_a_cmyk_measurement_into_an_rgb_run_is_refused(tmp_path):
    chart = _chart(tmp_path / "run.ti2", "iRGB")
    v = assess(_measurement(tmp_path / "m.ti3", "CMYK"), chart)
    assert not v.ok
    assert "measurement is CMYK" in v.reason and "RGB" in v.reason


def test_another_ink_set_is_refused(tmp_path):
    chart = _chart(tmp_path / "run.ti2", "CMYK")
    v = assess(_measurement(tmp_path / "m.ti3", "CMYKOG"), chart)
    assert not v.ok and "CMYKOG" in v.reason


def test_fewer_readings_are_a_partial_more_are_another_chart(tmp_path):
    chart = _chart(tmp_path / "run.ti2")
    short = assess(_measurement(tmp_path / "s.ti3", n=10), chart)
    assert short.ok and short.partial and short.n_measured == 10
    long_ = assess(_measurement(tmp_path / "l.ti3", n=N + 5), chart)
    assert not long_.ok and "different chart" in long_.reason


def test_a_file_without_colour_is_no_measurement(tmp_path):
    chart = _chart(tmp_path / "run.ti2")
    v = assess(_measurement(tmp_path / "m.ti3", xyz=False), chart)
    assert not v.ok and "No XYZ or Lab" in v.reason


def test_the_rgb_path_is_unchanged(tmp_path):
    chart = _chart(tmp_path / "run.ti2", "iRGB")
    assert assess(_measurement(tmp_path / "m.ti3", "iRGB"), chart).ok


def test_a_device_less_export_still_takes_the_name_pairing(tmp_path):
    """§I.11 unchanged: no device columns is not the wrong device columns."""
    chart = _chart(tmp_path / "run.ti2", "iRGB")
    p = tmp_path / "bare.ti3"
    rows = [f'{i + 1} "A{N - i}" {20 + i}.0 {21 + i}.0 {22 + i}.0'
            for i in range(N)]
    p.write_text('CTI3\n\nNUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\n'
                 'SAMPLE_ID SAMPLE_LOC XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n'
                 f'NUMBER_OF_SETS {N}\nBEGIN_DATA\n' + "\n".join(rows)
                 + '\nEND_DATA\n', encoding="utf-8")
    v = assess(p, chart)
    assert v.ok and v.device_from_chart


# --- 2. every door asks the rule ---------------------------------------------
def test_the_measure_tabs_doors_judge_through_assess(tmp_path):
    """Both run types of the IMPORT module, through the one wrapper."""
    from ui.tabs.tab_measure import TabMeasure
    chart = _chart(tmp_path / "run.ti2")
    assert TabMeasure._import_verdict(None, _measurement(tmp_path / "a.ti3"),
                                      chart).ok
    assert not TabMeasure._import_verdict(
        None, _measurement(tmp_path / "b.ti3", salt=5), chart).ok
    assert not TabMeasure._import_verdict(
        None, _measurement(tmp_path / "c.ti3", "iRGB"), chart).ok
    assert not TabMeasure._import_verdict(
        None, _measurement(tmp_path / "d.ti3"),
        _chart(tmp_path / "rgb.ti2", "iRGB")).ok
    for door in (TabMeasure._import_into_verification,
                 TabMeasure._import_into_profiling_run):
        assert "_import_verdict(" in inspect.getsource(door), door


def test_a_calibration_run_still_cannot_import():
    """§I.9: one cal/ per project and no old/ archive. Unchanged here."""
    from ui.tabs.tab_measure import TabMeasure
    assert "is_calibration()" in inspect.getsource(TabMeasure._import_available)


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def parent(qapp):
    from PyQt6.QtWidgets import QWidget
    w = QWidget()
    yield w
    w.deleteLater()


def _project(tmp_path, rep: str):
    from PyQt6.QtCore import QSettings
    from core.file_manager import FileManager, Project
    from core.settings import AppSettings
    root = tmp_path / "out"
    root.mkdir()
    proj = Project.create(root / "InkProbe", "InkProbe")
    run = proj.current_run()
    run.ensure_dir()
    _chart(run.chart_ti2, rep)
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    fm.set_target_name("InkProbe")
    return proj, run, fm


def _answer_everything(monkeypatch) -> list:
    """Say yes to every question; record every InfoDialog."""
    from PyQt6.QtWidgets import QMessageBox
    from ui import tooltip_button
    said: list = []

    def click_yes(self):
        for b in self.buttons():
            if self.buttonRole(b) == QMessageBox.ButtonRole.AcceptRole:
                b.click()
                return 0
        return 0
    monkeypatch.setattr(QMessageBox, "exec", click_yes)
    real_init = tooltip_button.InfoDialog.__init__

    def init(self, title, body, *a, **k):
        said.append((title, body))
        real_init(self, title, body, *a, **k)
    monkeypatch.setattr(tooltip_button.InfoDialog, "__init__", init)
    monkeypatch.setattr(tooltip_button.InfoDialog, "exec", lambda self: 0)
    return said


@pytest.mark.parametrize("measured,chart_rep,salt,filed", [
    ("CMYK", "CMYK", 0, True),       # CMYK into a CMYK run
    ("CMYK", "CMYK", 9, False),      # CMYK of another chart
    ("iRGB", "CMYK", 0, False),      # RGB into a CMYK run
    ("CMYK", "iRGB", 0, False),      # CMYK into an RGB run
])
def test_build_profiles_load_measurement_door(parent, tmp_path, monkeypatch,
                                              measured, chart_rep, salt, filed):
    """Build Profile -> "Load measurement data" on a file outside the project:
    `file_into_project`, the door `_offer_import_into_a_project` opens."""
    from ui import measurement_filing as mf
    proj, run, fm = _project(tmp_path, chart_rep)
    src = _measurement(tmp_path / "export.ti3", measured, salt=salt)
    said = _answer_everything(monkeypatch)
    got: list = []
    mf.file_into_project(parent, "InkProbe", src, fm, None,
                         on_filed=got.append)
    if filed:
        assert got, said
        assert device_space_of(Path(got[0])) == "CMYK"
        assert not any("does not belong" in t for t, _ in said), said
    else:
        assert not got, f"filed a measurement of another chart: {got}"
        assert any("does not belong" in t for t, _ in said), said


# --- 3. the i1Profiler CxF converter ------------------------------------------
_CXF_NS = 'xmlns:cc="http://colorexchangeformat.com/CxF3-core"'


def _cxf(path: Path, kinds: "list[str]") -> Path:
    objs = []
    for i, kind in enumerate(kinds):
        if kind == "CMYK":
            dev = ('<cc:ColorCMYK><cc:Cyan>{0}</cc:Cyan><cc:Magenta>{1}'
                   '</cc:Magenta><cc:Yellow>0</cc:Yellow><cc:Black>0'
                   '</cc:Black></cc:ColorCMYK>').format(i * 10, 100 - i * 10)
        else:
            dev = ('<cc:ColorRGB><cc:R>255</cc:R><cc:G>{0}</cc:G><cc:B>0'
                   '</cc:B></cc:ColorRGB>').format(i * 20)
        objs.append(f'<cc:Object ObjectType="Target" Name="T{i}" Id="t{i}">'
                    f'<cc:DeviceColorValues>{dev}</cc:DeviceColorValues>'
                    '</cc:Object>')
    spec = " ".join(["50"] * 36)
    for i in range(len(kinds)):
        objs.append(f'<cc:Object ObjectType="M0_Measurement" Name="M{i}" '
                    f'Id="m{i}"><cc:ColorValues><cc:ReflectanceSpectrum '
                    f'StartWL="380">{spec}</cc:ReflectanceSpectrum>'
                    '</cc:ColorValues></cc:Object>')
    path.write_text(
        f'<?xml version="1.0"?><cc:CxF {_CXF_NS}><cc:Resources>'
        f'<cc:ObjectCollection>{"".join(objs)}</cc:ObjectCollection>'
        '</cc:Resources></cc:CxF>', encoding="utf-8")
    return path


def test_a_cmyk_cxf_converts_to_a_cmyk_measurement(tmp_path):
    from workflow.printer_calibration import read_table
    from workflow.reference_convert import cxf_measurement_to_ti3
    out = cxf_measurement_to_ti3(_cxf(tmp_path / "m.mxf", ["CMYK"] * 3),
                                 tmp_path / "m.ti3")
    fields, rows, kw = read_table(out)
    assert kw["COLOR_REP"] == "CMYK_XYZ"
    assert fields[2:6] == ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"]
    # ColorCMYK is percent already: Cyan 20 stays 20, not 7.8
    assert float(rows["3"]["CMYK_C"]) == pytest.approx(20.0)
    assert float(rows["3"]["CMYK_M"]) == pytest.approx(80.0)


def test_an_rgb_cxf_is_unchanged(tmp_path):
    from workflow.reference_convert import cxf_measurement_to_ti3
    out = cxf_measurement_to_ti3(_cxf(tmp_path / "m.mxf", ["RGB"] * 2),
                                 tmp_path / "m.ti3")
    d = parse_ti3(out)
    assert d.keywords["COLOR_REP"] == "iRGB_XYZ"
    assert d.rgb[1][1] == pytest.approx(20 * 100 / 255, abs=1e-3)


def test_a_cxf_that_mixes_device_spaces_is_refused(tmp_path):
    from workflow.reference_convert import (ReferenceConvertError,
                                            cxf_measurement_to_ti3)
    with pytest.raises(ReferenceConvertError, match="RGB or CMYK"):
        cxf_measurement_to_ti3(_cxf(tmp_path / "m.mxf", ["RGB", "CMYK"]),
                               tmp_path / "m.ti3")


# --- 4. the RGB-only views ------------------------------------------------------
def test_the_rgb_only_note_names_the_inks(tmp_path):
    from workflow import measurement_messages as M
    title, body = non_rgb_note(_measurement(tmp_path / "m.ti3", "CMYKOG"))
    assert title == M.M_VIEW_RGB_ONLY.title
    assert "CMYKOG measurement" in body
    assert non_rgb_note(_measurement(tmp_path / "r.ti3", "iRGB")) is None
    assert non_rgb_note(None) is None


def test_the_patch_identity_check_says_rgb_only_for_a_cmyk_chart(tmp_path):
    from workflow import measurement_messages as M
    from workflow.measurement_report import verify_patch_identity
    rgb = parse_ti3(_measurement(tmp_path / "r.ti3", "iRGB"))
    out = verify_patch_identity(rgb, _chart(tmp_path / "c.ti2", "CMYK"))
    assert out["verdict"] == "unchecked"
    assert out["reason"] == M.M_VIEW_RGB_ONLY.title


def test_the_measurement_details_window_shows_the_note(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    from workflow import measurement_messages as M
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    from core.argyll_runner import ArgyllRunner
    d = Ti3InfoDialog(ArgyllRunner(s), s)
    d.load_measurement(_measurement(tmp_path / "m.ti3"))
    assert M.M_VIEW_RGB_ONLY.title in d._banner.text()
    assert "Could not read" not in d._banner.text()
    d.deleteLater()


def test_the_report_window_shows_the_note(qapp, tmp_path, monkeypatch):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow import measurement_messages as M
    pages: list = []
    real = MeasurementReportDialog._show_no_report
    monkeypatch.setattr(MeasurementReportDialog, "_show_no_report",
                        lambda self, html: (pages.append(html),
                                            real(self, html))[1])
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    run = tmp_path / "run1"
    run.mkdir()
    _chart(run / "P.ti2")
    ti3 = _measurement(run / "P.ti3")
    d = MeasurementReportDialog(s, None, initial_ti3=ti3)
    try:
        assert any(M.M_VIEW_RGB_ONLY.title in h for h in pages), pages
        assert not any("Could not read" in h for h in pages), pages
        assert d._page_drawn is False
    finally:
        d.deleteLater()


def test_the_automatic_report_says_it_in_the_log_and_saves_nothing():
    """`_maybe_save_measurement_report` asks the note before `build_report`."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._maybe_save_measurement_report)
    assert src.index("non_rgb_note") < src.index("build_report(")
