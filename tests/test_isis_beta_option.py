"""THE i1iSis CHART BETA WITH THE OPTION ON: the Preferences row and its
consent window, the Measure tab's window, the i1Profiler files, and the
Guided entry (2026-11-14)."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TARGEN = Path("/Applications/Argyll/bin/targen")
requires_argyll = pytest.mark.skipif(
    not _TARGEN.exists() and shutil.which("targen") is None,
    reason="ArgyllCMS targen is not installed here")


@pytest.fixture(autouse=True)
def isis_on():
    from workflow.isis import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def test_preferences_has_the_row_and_switching_on_asks_first(qapp, tmp_path,
                                                             monkeypatch):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QMessageBox
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    dlg = SettingsDialog(s)
    try:
        box = dlg._isis_charts_check
        assert box.text() == "X-Rite i1iSis charts (beta)"
        assert not box.isChecked()
        asked = []

        def answer(result):
            def _exec(self):
                asked.append(self.text())
                return result
            return _exec
        monkeypatch.setattr(QMessageBox, "exec",
                            answer(QMessageBox.StandardButton.Cancel))
        box.click()
        assert not box.isChecked() and len(asked) == 1
        assert "own risk" in asked[0]
        monkeypatch.setattr(QMessageBox, "exec",
                            answer(QMessageBox.StandardButton.Ok))
        box.click()
        assert box.isChecked() and len(asked) == 2
        box.click()
        assert not box.isChecked() and len(asked) == 2
        box.click()
        assert box.isChecked() and len(asked) == 3
    finally:
        dlg.deleteLater()


def test_the_help_and_the_consent_say_what_this_is():
    from ui.dialogs.settings_dialog import isis_charts_help, isis_consent_text
    help_, consent = isis_charts_help(), isis_consent_text()
    for text in (help_, consent):
        assert "i1Profiler" in text
        assert "—" not in text
        assert "own risk" in text
    assert "sends nothing" in help_ and "sends nothing" in consent
    assert "Default:** off" in help_
    assert "nothing else changes" in help_


def test_the_default_is_off():
    from core.settings import DEFAULTS
    assert DEFAULTS["isis_charts_beta"] is False


def _chart(tmp_path, name="X-Rite i1iSis"):
    ti2 = tmp_path / "isischart.ti2"
    ti2.write_text(
        "CTI2\n\n"
        'DESCRIPTOR "Argyll Calibration Target chart information 2"\n'
        f'TARGET_INSTRUMENT "{name}"\nCOLOR_REP "RGB"\n'
        "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\nNUMBER_OF_SETS 1\nBEGIN_DATA\n"
        '1 "A1" 100 100 100 95 100 108\nEND_DATA\n', encoding="utf-8")
    ti2.with_suffix(".ti1").write_text(ti2.read_text(encoding="utf-8")
                                       .replace("CTI2", "CTI1", 1),
                                       encoding="utf-8")
    (tmp_path / "isischart.isis.json").write_text(json.dumps(
        {"columns": 28, "rows": 35, "pages": 2, "fed_as_printed": False}),
        encoding="utf-8")
    return ti2


@pytest.fixture
def measure_tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabMeasure(ArgyllRunner(s), s)
    yield t
    t.close()
    t.deleteLater()


def test_start_on_an_i1isis_chart_explains_the_i1profiler_way(
        measure_tab, tmp_path, monkeypatch):
    """At the very top of Start, before anything is recovered or armed:
    M-ISIS-NOT-YET filled from the chart (its .txf, the grid, the cut,
    several pages said)."""
    tab = measure_tab
    shown = []
    monkeypatch.setattr(type(tab), "_i1io_window",
                        lambda self, t, b: shown.append((t, b)))
    tab.set_ti1_path(_chart(tmp_path).with_suffix(".ti1"))
    monkeypatch.setattr(tab, "_recover_engine_autosave", lambda: pytest.fail(
        "Start went past the i1iSis notice"))
    tab._on_start()
    assert len(shown) == 1
    title, body = shown[0]
    assert title == "Measuring with an i1iSis happens in i1Profiler"
    for part in ("isischart-i1profiler-isis.txf", "28 columns", "35 rows",
                 "and 2 pages", "Cut the sheet along the dashed outline",
                 "This chart has 2 pages", "Import Measurement",
                 "Dual scan", "(M2)"):
        assert part in body, part
    assert "—" not in title + body
    assert "i1Profiler" in tab._log.toPlainText()


def test_an_ordinary_chart_is_not_taken_for_an_i1isis_one(measure_tab,
                                                          tmp_path):
    measure_tab.set_ti1_path(_chart(tmp_path, "GretagMacbeth i1 Pro")
                             .with_suffix(".ti1"))
    assert measure_tab._refused_as_an_isis_chart() is False


def test_i1profilers_own_name_is_not_a_chromiq_chart():
    from workflow.isis.support import is_isis_instrument_name
    assert is_isis_instrument_name('"X-Rite i1iSis"')
    assert is_isis_instrument_name("x-rite i1isis 2")
    assert not is_isis_instrument_name("i1iSis")
    assert not is_isis_instrument_name("X-Rite i1iO")


def test_the_messages_are_proposed_and_dashless():
    from workflow import measurement_messages as M
    for m in (M.M_ISIS_NOT_YET, M.M_ISIS_SUPPORT_OFF, M.M_ISIS_SHEET_CHECK):
        assert m.approved is False
        assert "—" not in m.title + m.body


@requires_argyll
def test_the_i1profiler_files_name_the_device_and_force_the_grid(tmp_path):
    """A real build (targen + the engine): the .txf names the device and
    gives a page that makes i1Profiler compute ChromIQ's grid, every printed
    cell is in it in placement order with ChromIQ's name, and the .pxf
    names the device too."""
    import re
    import subprocess
    from workflow.chart_exports import write_sidecars
    from workflow.isis import export as X
    from workflow.isis.support import read_side_file
    from workflow.layout_engine.chart import build_chart
    targen = str(_TARGEN if _TARGEN.exists() else shutil.which("targen"))
    subprocess.run([targen, "-d2", "-f300", "-G", str(tmp_path / "t")],
                   check=True, capture_output=True, timeout=120)
    build_chart(tmp_path / "t.ti1", tmp_path / "t", instrument="XRISIS",
                paper="A4", dpi=72, project="Txf_Test", isis_model="xl",
                isis_tight=True, isis_header_mm=40.0, patch_w=8.0, patch_h=7.0)
    written = write_sidecars(tmp_path / "t.ti1", tmp_path / "exports", "t")
    txf = tmp_path / "exports" / "t-i1profiler-isis.txf"
    assert txf in written
    text = txf.read_text(encoding="utf-8")
    attr = dict(re.findall(r'(\w+)="([^"]*)"',
                           re.search(r"<xrp:CustomAttributes([^>]*)/>",
                                     text).group(1)))
    side = read_side_file(tmp_path / "t.ti2")
    assert attr["MeasurementDevice"] == "i1iSis XL"
    assert attr["TightMarginsEnabled"] == "True"
    assert attr["BarCodeEnabled"] == "False"
    assert attr["PaperFormat"] == "Custom"
    assert attr["UsePatchSettingDefaults"] == "False"
    assert attr["ScramblePatches"] == "False"
    assert float(attr["PatchSizeWidthPercent"]) == pytest.approx(
        (8 - 6) / 14 * 100)
    assert float(attr["PatchSizeHeightPercent"]) == pytest.approx(
        (7 - 6) / 14 * 100)
    assert float(attr["HeaderEdgeSizePercent"]) == pytest.approx(
        (40 - 32) / 48 * 100)
    d = X.TxfDesign(device=attr["MeasurementDevice"],
                    page_w=float(attr["PageWidth"]),
                    page_h=float(attr["PageHeight"]),
                    margins=tuple(float(attr[f"PrintMargin{k}"]) for k in
                                  ("Top", "Right", "Bottom", "Left")),
                    pw=8.0, ph=7.0, header=40.0, tight=True, barcode=False,
                    columns=0, rows=0, pages=0)
    assert X.i1profiler_grid(d, int(attr["numberCorePatches"])) == (
        side["columns"], side["rows"], side["pages"])
    names = re.findall(r'Name="SampleName" Value="([^"]*)"', text)
    order = json.loads((tmp_path / "exports" / "t-i1profiler-isis.order.json")
                       .read_text(encoding="utf-8"))
    assert names == [e["loc"] for e in order["order"]]
    assert len(names) == side["patches"] == 300
    pxf = (tmp_path / "exports" / "t-i1profiler.pxf").read_text("utf-8")
    assert 'MeasurementDevice="i1iSis XL"' in pxf
