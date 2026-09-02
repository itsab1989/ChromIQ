"""Knut's beta.29/.31 follow-ups:

1. Convert i1Profiler → TI3: picking a *second* input file must update the
   auto-filled output name (it used to stay stuck on the first file's stem).
2. Measurement Report → Add measurement: the picker must accept i1Profiler
   files (.mxf/.txt/.cxf) directly and convert them — no export step."""
import os
import types
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    from core.settings import AppSettings

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    return s


# --- Issue 2: Convert dialog auto-name follows each new input file -----------

def test_convert_output_name_follows_each_input(qapp, settings):
    from core.argyll_runner import ArgyllRunner
    from ui.dialogs.tools_dialogs import I1ProfilerToTi3Dialog

    dlg = I1ProfilerToTi3Dialog(ArgyllRunner(settings), settings)

    def pick(path):
        dlg._pick_input_file = lambda *a, **k: Path(path)
        dlg._pick_txt()

    pick("/data/Epson-P900_2026-01-06.txt")
    assert dlg._output.name == "Epson-P900_2026-01-06"
    # Second file → name UPDATES (the bug: it stayed on the first stem).
    pick("/data/Epson-P900_2026-01-20.txt")
    assert dlg._output.name == "Epson-P900_2026-01-20"


def test_convert_keeps_a_name_the_user_typed(qapp, settings):
    from core.argyll_runner import ArgyllRunner
    from ui.dialogs.tools_dialogs import I1ProfilerToTi3Dialog

    dlg = I1ProfilerToTi3Dialog(ArgyllRunner(settings), settings)
    dlg._pick_input_file = lambda *a, **k: Path("/data/first.txt")
    dlg._pick_txt()
    dlg._output._name_edit.setText("my-custom-name")          # user overrides
    dlg._pick_input_file = lambda *a, **k: Path("/data/second.txt")
    dlg._pick_txt()
    assert dlg._output.name == "my-custom-name"                # preserved


# --- Issue 1: Measurement Report accepts i1Profiler files directly -----------

def test_report_as_ti3_passthrough(qapp, settings, tmp_path):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog

    host = types.SimpleNamespace(
        _settings=settings,
        _view=types.SimpleNamespace(setHtml=lambda _h: None))
    ti3 = tmp_path / "m.ti3"
    ti3.write_text("x", encoding="utf-8")
    assert MeasurementReportDialog._as_ti3(host, ti3) == ti3   # used as-is


def test_report_as_ti3_converts_i1profiler(qapp, settings, tmp_path, monkeypatch):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog

    seen = {}

    def fake_convert(src, argyll, out_dir):
        seen["src"] = Path(src)
        out = Path(out_dir) / f"{Path(src).stem}.ti3"
        out.write_text("y", encoding="utf-8")
        return out

    monkeypatch.setattr(
        "workflow.reference_convert.convert_i1profiler_measurement", fake_convert)
    host = types.SimpleNamespace(
        _settings=settings,
        _view=types.SimpleNamespace(setHtml=lambda _h: None))
    txt = tmp_path / "Epson-P900_2026-01-06.txt"
    txt.write_text("z", encoding="utf-8")
    out = MeasurementReportDialog._as_ti3(host, txt)
    assert out is not None and out.suffix == ".ti3"
    assert out.stem == "Epson-P900_2026-01-06"                 # stem preserved
    assert seen["src"] == txt


def test_report_pdf_anchors_on_origin_not_temp(qapp, tmp_path, monkeypatch):
    """Imported measurements convert into a temp folder, but the PDF / Reveal must
    default to the user's ORIGINAL folder, never the temp one (Knut)."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog as M

    monkeypatch.setattr(
        "workflow.measurement_report.list_project_reports", lambda d: [])
    origin = tmp_path / "myfolder" / "Epson_2026-01-06.txt"
    origin.parent.mkdir(parents=True)
    origin.write_text("x", encoding="utf-8")
    temp_ti3 = tmp_path / "chromiq_report_xyz" / "Epson_2026-01-06.ti3"
    temp_ti3.parent.mkdir()
    temp_ti3.write_text("y", encoding="utf-8")

    host = types.SimpleNamespace(_sources=[], _ti3=None)
    host._source_key = types.MethodType(M._source_key, host)
    host._gather_runs = lambda t: (t.stem, [{"created": "2026-01-01"}])
    types.MethodType(M._append_source, host)(temp_ti3, origin=origin)

    anchor = types.MethodType(M._anchor_dir, host)()
    assert anchor == origin.parent                 # user's folder…
    assert anchor != temp_ti3.parent               # …not the temp conversion folder


def test_report_as_ti3_raises_on_bad_file(qapp, settings, tmp_path, monkeypatch):
    """_as_ti3 raises on a bad file so the batch adder can list what failed."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog

    def boom(src, argyll, out_dir):
        raise ValueError("not an i1Profiler file")

    monkeypatch.setattr(
        "workflow.reference_convert.convert_i1profiler_measurement", boom)
    host = types.SimpleNamespace(_settings=settings)
    with pytest.raises(ValueError):
        MeasurementReportDialog._as_ti3(host, tmp_path / "bad.txt")


# --- Knut beta.31/.32 follow-up: many measurements from one folder ----------

def test_source_key_standalone_by_file_project_by_folder(qapp, tmp_path, monkeypatch):
    """Standalone/imported measurements key by FILE (so several in one folder each
    add); a ChromIQ project keys by FOLDER (all its runs = one source)."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog as M

    host = types.SimpleNamespace()
    key = types.MethodType(M._source_key, host)
    ti3 = tmp_path / "m.ti3"
    ti3.write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        "workflow.measurement_report.list_project_reports", lambda d: [])
    assert key(ti3) == ("file", str(ti3))
    monkeypatch.setattr(
        "workflow.measurement_report.list_project_reports",
        lambda d: [tmp_path / "r.json"])
    assert key(ti3) == ("dir", str(tmp_path))


def test_several_loose_ti3_in_one_folder_each_add(qapp, tmp_path, monkeypatch):
    """The bug: two .ti3 in the same folder collapsed to one. Now each adds; the
    same file twice still dedups."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog as M

    monkeypatch.setattr(
        "workflow.measurement_report.list_project_reports", lambda d: [])
    a = tmp_path / "m1.ti3"; a.write_text("x", encoding="utf-8")
    b = tmp_path / "m2.ti3"; b.write_text("y", encoding="utf-8")
    host = types.SimpleNamespace(_sources=[], _ti3=None)
    host._source_key = types.MethodType(M._source_key, host)
    host._gather_runs = lambda ti3: (ti3.stem, [{"created": "2026-01-01"}])
    append = types.MethodType(M._append_source, host)
    assert append(a) is True
    assert append(b) is True          # same folder, different file → both added
    assert append(a) is False         # same file again → deduped
    assert len(host._sources) == 2
    assert {s["name"] for s in host._sources} == {"m1", "m2"}
