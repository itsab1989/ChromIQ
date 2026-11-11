"""An i1Profiler CGATS text export written with DECIMAL COMMAS imports.

Found in the 4.3.32 review (2026-11-11): i1Profiler on a decimal-comma system
(German, say) writes its CGATS text export as ``0,056192``, and every door
that imports an i1Profiler ``.txt`` handed it to ArgyllCMS ``txt2ti3`` as it
was. txt2ti3 refuses it ("Field 'RGB_R' has unexpected type, should be
'real', is 'non-quoted char string'"), and the person read "The file could
not be converted". 4.3.29 fixed the same thing for i1Profiler's ``.mxf`` /
CxF files; this is that rule for the CGATS text export, in ONE helper
(`reference_convert.cgats_decimal_points` / `decimal_point_source`) used by
`convert_i1profiler_measurement`, by the two doors that run txt2ti3
themselves, and by Another reading (`reading_compare`), which had its own
copy of the rule until now.

The rule, as for CxF: a value is a decimal comma only when it is digits, one
comma and digits, and only when no number in the data block carries a point.
Only number cells of the data block and the spectral range keywords are
touched; quoted text, name columns and header text keep their commas. A file
that mixes the two forms, or holds a value that is no number in either, is
left as it is, and txt2ti3 refuses it as it always did. The person's file is
never written, and the temporary copy is removed.

The fixtures are shaped like a real i1Profiler export (tab-separated,
i1Profiler's column names, XYZ and spectra on the 0..1 scale), built from the
suite's own ET-8550 verification reading, never from a tester's file.
"""
from __future__ import annotations

import inspect
import os
import tempfile
import types
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M                  # noqa: E402
from workflow.reference_convert import (                        # noqa: E402
    ReferenceConvertError, cgats_decimal_points,
    convert_i1profiler_measurement, decimal_point_source)

SRC = (Path(__file__).parent / "data" / "g_basti_et8550_run1_verify"
       / "ET8550_EpsPremSG_AdobeRGB_CM_Okt26-verify.ti3")
ROWS = 60               # enough patches for txt2ti3, fast enough for the suite


def _argyll() -> str:
    from tests.argyll_env import argyll_bin_dir, argyll_tool
    if argyll_tool("txt2ti3") is None or argyll_tool("spec2cie") is None:
        pytest.skip("ArgyllCMS txt2ti3 / spec2cie are not installed")
    return str(argyll_bin_dir())


def _rows():
    lines = SRC.read_text(encoding="utf-8").splitlines()
    fields = lines[lines.index("BEGIN_DATA_FORMAT") + 1].split()
    d0 = lines.index("BEGIN_DATA")
    return fields, [ln.split() for ln in lines[d0 + 1:d0 + 1 + ROWS]]


def _lab(x, y, z):
    w = (96.42, 100.0, 82.49)

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    fx, fy, fz = (f(v / n) for v, n in zip((x, y, z), w))
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def _export(out: Path, *, rgb=True, xyz=False, lab=False, spectral=False,
            sep="\t", comma=False, names=None) -> Path:
    """The ET-8550 reading as i1Profiler's CGATS text export writes one.
    The header carries commas that are TEXT ("ILLUMINANT, D50",
    "11,5 mm"); *comma* writes every number of the data block with a
    decimal comma, as i1Profiler does on a decimal-comma system."""
    fields, rows = _rows()
    fi = {f: i for i, f in enumerate(fields)}
    spec = [f for f in fields if f.startswith("SPEC_")]
    head = ["SAMPLE_ID", "SAMPLE_NAME"]
    head += ["RGB_R", "RGB_G", "RGB_B"] if rgb else []
    head += ["XYZ_X", "XYZ_Y", "XYZ_Z"] if xyz else []
    head += ["LAB_L", "LAB_A", "LAB_B"] if lab else []
    head += [f"SPECTRAL_NM{f[5:]}" for f in spec] if spectral else []
    body = []
    for n, r in enumerate(rows):
        name = names[n] if names else r[fi["SAMPLE_LOC"]].strip('"')
        v = [r[fi["SAMPLE_ID"]], name]
        nums = []
        if rgb:
            nums += [f"{float(r[fi[f'RGB_{c}']]) * 2.55:.2f}" for c in "RGB"]
        X, Y, Z = (float(r[fi[f"XYZ_{c}"]]) for c in "XYZ")
        if xyz:
            nums += [f"{t / 100:.6f}" for t in (X, Y, Z)]
        if lab:
            nums += [f"{t:.2f}" for t in _lab(X, Y, Z)]
        if spectral:
            nums += [f"{float(r[fi[f]]) / 100:.6f}" for f in spec]
        if comma:
            nums = [t.replace(".", ",") for t in nums]
        body.append(sep.join(v + nums))
    text = (
        "CGATS.17\n\n"
        f'ORIGINATOR{sep}"i1Profiler - X-Rite, Inc."\n'
        f'INSTRUMENTATION{sep}"i1Pro 3 ; Serial number 0"\n'
        f'DESCRIPTOR{sep}"Chart with 11,5 mm patches, 1,5 pages"\n'
        f'MEASUREMENT_SOURCE{sep}"MeasurementCondition=M2\tFilter=UVcut"\n'
        f'WEIGHTING_FUNCTION{sep}"ILLUMINANT, D50"\n'
        f'WEIGHTING_FUNCTION{sep}"OBSERVER, 2 degree"\n'
        f'CREATED{sep}"2026-11-11T20:00:00"\n\n'
        f"NUMBER_OF_FIELDS{sep}{len(head)}\nBEGIN_DATA_FORMAT\n"
        + sep.join(head) + "\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS{sep}{len(body)}\nBEGIN_DATA\n" + "\n".join(body)
        + "\nEND_DATA\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


def _table(ti3: Path) -> str:
    """The converted measurement's fields and values (txt2ti3's header
    carries the time of the conversion, which two runs never share)."""
    t = ti3.read_text(encoding="utf-8")
    return t[t.index("BEGIN_DATA_FORMAT"):]


def _leftovers() -> list:
    return sorted(Path(tempfile.gettempdir()).glob("chromiq-decimal-points-*"))


VARIANTS = {
    "lab+rgb": dict(lab=True),
    "xyz+rgb": dict(xyz=True),
    "spectral+rgb": dict(spectral=True),
    "everything": dict(xyz=True, lab=True, spectral=True),
    "lab, no rgb": dict(rgb=False, lab=True),
    "spectral, no rgb": dict(rgb=False, spectral=True),
}


# ---- every variant imports as its point-decimal twin ----------------------

@pytest.mark.parametrize("sep", ["\t", " "], ids=["tab", "space"])
@pytest.mark.parametrize("kind", list(VARIANTS))
def test_a_comma_export_imports_exactly_as_its_point_twin(tmp_path, kind, sep):
    argyll = _argyll()
    point = _export(tmp_path / "point" / "export.txt", sep=sep,
                    **VARIANTS[kind])
    comma = _export(tmp_path / "comma" / "export.txt", sep=sep, comma=True,
                    **VARIANTS[kind])
    before = comma.read_bytes()
    assert "0," in comma.read_text(encoding="utf-8")
    a = convert_i1profiler_measurement(point, argyll, tmp_path / "out-point")
    b = convert_i1profiler_measurement(comma, argyll, tmp_path / "out-comma")
    assert _table(b) == _table(a)
    assert comma.read_bytes() == before          # the person's file, untouched
    assert _leftovers() == []                    # the temporary copy is gone


def test_the_import_stamps_the_header_from_the_persons_own_file(tmp_path):
    argyll = _argyll()
    comma = _export(tmp_path / "export.txt", comma=True, lab=True)
    out = convert_i1profiler_measurement(comma, argyll, tmp_path / "out")
    text = out.read_text(encoding="utf-8")
    assert 'MEASUREMENT_CONDITION "M2"' in text
    assert "i1Pro 3" in text


# ---- what is refused stays refused, in the words it always had -----------

@pytest.mark.parametrize("old,new,why", [
    (",", ".", "one value with a point among commas"),
    ("\t", "\t1.234,5\t", "a thousands separator, 1.234,5"),
    ("\t", "\t1,234.5\t", "a thousands separator, 1,234.5"),
    ("\t", "\tn/a\t", "a value that is no number"),
], ids=["mixed", "thousands-de", "thousands-en", "not-a-number"])
def test_a_file_that_does_not_say_how_it_writes_numbers_is_refused(
        tmp_path, old, new, why):
    argyll = _argyll()
    p = _export(tmp_path / "export.txt", comma=True, lab=True)
    t = p.read_text(encoding="utf-8")
    d = t.index("BEGIN_DATA\n") + len("BEGIN_DATA\n")
    row_end = t.index("\n", d)
    row = t[d:row_end]
    if old == ",":
        row = row.replace(",", ".", 1)
    else:
        cells = row.split("\t")
        cells[3] = new.strip("\t")
        row = "\t".join(cells)
    p.write_text(t[:d] + row + t[row_end:], encoding="utf-8")
    before = p.read_bytes()
    with pytest.raises(ReferenceConvertError) as e:
        convert_i1profiler_measurement(p, argyll, tmp_path / "out")
    # The 4.3.29 kind of refusal: ArgyllCMS's own reason, in a §M message
    # in the person's language, nothing guessed.
    assert e.value.message_id == M.M_CONVERT_TOOL_FAILED.id, why
    assert "has unexpected type" in str(e.value)
    # ArgyllCMS's line names the person's file, never the temporary copy.
    assert "chromiq-decimal-points" not in str(e.value)
    assert str(p) in str(e.value)
    assert p.read_bytes() == before
    assert _leftovers() == []


# ---- the rule itself: only numbers, only where a number belongs ----------

_DOC = (
    'CGATS.17\r\n'
    'DESCRIPTOR\t"11,5 mm, 1,5 pages"\r\n'
    'WEIGHTING_FUNCTION\t"ILLUMINANT, D50"\r\n'
    'SPECTRAL_START_NM\t"380,0"\r\n'
    'SPECTRAL_END_NM 730,0\r\n'
    'NUMBER_OF_FIELDS\t5\r\n'
    'BEGIN_DATA_FORMAT\r\n'
    'SAMPLE_ID\tSAMPLE_NAME\tSAMPLE_LOC\tLAB_L\tLAB_A\r\n'
    'END_DATA_FORMAT\r\n'
    'NUMBER_OF_SETS\t2\r\n'
    'BEGIN_DATA\r\n'
    '1\t1,5\t"A,1"\t95,25\t-0,50\r\n'
    '2\tB2\t"B, 2"\t8,5e+01\t255\r\n'
    'END_DATA\r\n')


def test_only_number_cells_and_spectral_range_keywords_change():
    got = cgats_decimal_points(_DOC)
    assert got == (
        'CGATS.17\r\n'
        'DESCRIPTOR\t"11,5 mm, 1,5 pages"\r\n'
        'WEIGHTING_FUNCTION\t"ILLUMINANT, D50"\r\n'
        'SPECTRAL_START_NM\t"380.0"\r\n'
        'SPECTRAL_END_NM 730.0\r\n'
        'NUMBER_OF_FIELDS\t5\r\n'
        'BEGIN_DATA_FORMAT\r\n'
        'SAMPLE_ID\tSAMPLE_NAME\tSAMPLE_LOC\tLAB_L\tLAB_A\r\n'
        'END_DATA_FORMAT\r\n'
        'NUMBER_OF_SETS\t2\r\n'
        'BEGIN_DATA\r\n'
        '1\t1,5\t"A,1"\t95.25\t-0.50\r\n'
        '2\tB2\t"B, 2"\t8.5e+01\t255\r\n'
        'END_DATA\r\n')


@pytest.mark.parametrize("cell", ["95.25", "1.234,5", "1,234.5"])
def test_a_mixed_data_block_is_left_as_it_is(cell):
    assert cgats_decimal_points(_DOC.replace("95,25", cell)) is None


def test_a_point_file_a_ragged_row_and_no_table_are_left_as_they_are():
    point = _DOC.replace("95,25", "95.25").replace("-0,50", "-0.50") \
        .replace("8,5e+01", "85")
    assert cgats_decimal_points(point) is None              # nothing to do
    assert cgats_decimal_points(_DOC.replace("\t255", "")) is None
    assert cgats_decimal_points("CGATS.17\nDESCRIPTOR \"1,5\"\n") is None


def test_the_temporary_copy_keeps_the_name_and_goes_away(tmp_path):
    p = _export(tmp_path / "Epson P900 v1.2.txt", comma=True, lab=True)
    before = p.read_bytes()
    with decimal_point_source(p) as src:
        assert src != p and src.name == p.name and src.is_file()
        assert "," not in src.read_text(encoding="utf-8").split(
            "BEGIN_DATA\n", 1)[1].split("END_DATA")[0]
    assert not src.exists() and not src.parent.exists()
    assert p.read_bytes() == before
    point = _export(tmp_path / "point.txt", lab=True)
    with decimal_point_source(point) as same:
        assert same == point                     # nothing to rewrite


def test_the_copy_goes_away_when_the_conversion_fails(tmp_path):
    p = _export(tmp_path / "export.txt", comma=True, lab=True)
    with pytest.raises(ReferenceConvertError):
        convert_i1profiler_measurement(p, tmp_path / "no-argyll-here",
                                       tmp_path / "out")
    assert _leftovers() == []


# ---- every door ------------------------------------------------------------

@pytest.fixture()
def settings(tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    return s


@pytest.fixture()
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _point_twin_table(tmp_path, argyll, **kw) -> str:
    point = _export(tmp_path / "twin" / "export.txt", **kw)
    return _table(convert_i1profiler_measurement(point, argyll,
                                                 tmp_path / "twin-out"))


def test_door_build_profile_import(tmp_path, settings):
    """Build Profile: Load measurement (`_convert_for_import`)."""
    argyll = _argyll()
    settings.set("argyll_bin_path", argyll)
    from ui.tabs.tab_profile import TabProfile
    src = _export(tmp_path / "in" / "export.txt", comma=True, lab=True)
    before = src.read_bytes()
    host = types.SimpleNamespace(_settings=settings)
    out = TabProfile._convert_for_import(host, src)
    try:
        assert out is not None
        assert _table(out) == _point_twin_table(tmp_path, argyll, lab=True)
    finally:
        import shutil
        shutil.rmtree(out.parent, ignore_errors=True)
    assert src.read_bytes() == before and _leftovers() == []


def test_door_calibration_measurement(tmp_path, settings):
    """Build Profile: a calibration measurement (printcal's .ti3)."""
    argyll = _argyll()
    settings.set("argyll_bin_path", argyll)
    from ui.tabs.tab_profile import TabProfile
    src = _export(tmp_path / "in" / "export.txt", comma=True, xyz=True)
    before = src.read_bytes()
    host = types.SimpleNamespace(
        _settings=settings,
        _pc_log=types.SimpleNamespace(appendPlainText=lambda _t: None))
    out = TabProfile._convert_calibration_measurement(host, src)
    assert out is not None and out.parent == src.parent
    assert _table(out) == _point_twin_table(tmp_path, argyll, xyz=True)
    assert src.read_bytes() == before and _leftovers() == []


def test_door_measurement_report_add(tmp_path, settings, qapp):
    """Measurement Report: Add measurement (`_as_ti3`)."""
    argyll = _argyll()
    settings.set("argyll_bin_path", argyll)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    src = _export(tmp_path / "in" / "export.txt", comma=True, spectral=True)
    before = src.read_bytes()
    host = types.SimpleNamespace(_settings=settings)
    out = MeasurementReportDialog._as_ti3(host, src)
    try:
        assert _table(out) == _point_twin_table(tmp_path, argyll,
                                                spectral=True)
    finally:
        for h in host._converted_tmpdirs:
            h.cleanup()
    assert src.read_bytes() == before and _leftovers() == []


class _SyncRunner:
    """ArgyllRunner's `run` contract, run to the end before it returns."""
    is_running = False

    def __init__(self, argyll):
        self.argyll = Path(argyll)
        self.calls = []

    def run(self, tool, args, cwd, on_line=None, on_finish=None, **_):
        import subprocess
        self.calls.append(list(args))
        r = subprocess.run([str(self.argyll / tool), *args], cwd=str(cwd),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120)
        for ln in (r.stdout + r.stderr).splitlines():
            if on_line:
                on_line(ln)
        if on_finish:
            on_finish(r.returncode)


def test_door_tools_convert_i1profiler_to_ti3(tmp_path, settings, qapp):
    """Tools > Convert i1Profiler > TI3 runs txt2ti3 itself."""
    argyll = _argyll()
    settings.set("argyll_bin_path", argyll)
    from ui.dialogs.tools_dialogs import I1ProfilerToTi3Dialog
    src = _export(tmp_path / "in" / "export.txt", comma=True, lab=True)
    before = src.read_bytes()
    runner = _SyncRunner(argyll)
    dlg = I1ProfilerToTi3Dialog(runner, settings)
    try:
        dlg._pick_input_file = lambda *a, **k: src
        dlg._pick_txt()
        dlg._output._dir_edit.setText(str(tmp_path / "out"))
        dlg._output._name_edit.setText("converted")
        dlg._execute()
        out = tmp_path / "out" / "converted.ti3"
        assert out.is_file(), dlg._log.toPlainText()
        assert _table(out) == _point_twin_table(tmp_path, argyll, lab=True)
        # The staged copy beside the result says what the person's file
        # says; txt2ti3 read a temporary copy that is gone again.
        assert (tmp_path / "out" / "converted.txt").read_bytes() == before
    finally:
        dlg.deleteLater()
    assert src.read_bytes() == before and _leftovers() == []


def test_door_tools_convert_into_the_files_own_name(tmp_path, settings, qapp):
    """Output folder and name the same as the input: the staged file IS the
    person's file, and it still is not written."""
    argyll = _argyll()
    settings.set("argyll_bin_path", argyll)
    from ui.dialogs.tools_dialogs import I1ProfilerToTi3Dialog
    src = _export(tmp_path / "in" / "export.txt", comma=True, lab=True)
    before = src.read_bytes()
    dlg = I1ProfilerToTi3Dialog(_SyncRunner(argyll), settings)
    try:
        dlg._pick_input_file = lambda *a, **k: src
        dlg._pick_txt()                    # defaults: its folder, its stem
        dlg._execute()
        assert (src.parent / "export.ti3").is_file()
    finally:
        dlg.deleteLater()
    assert src.read_bytes() == before and _leftovers() == []


def test_door_build_profile_txt_route(tmp_path, settings, monkeypatch):
    """Build Profile's own txt2ti3 route (`_import_i1profiler_txt`)."""
    argyll = _argyll()
    settings.set("argyll_bin_path", argyll)
    from ui.tabs.tab_profile import TabProfile
    import ui.txt_loader as txt_loader
    src = _export(tmp_path / "in" / "export.txt", comma=True, spectral=True)
    work = tmp_path / "project" / "export.txt"
    work.parent.mkdir()
    work.write_bytes(src.read_bytes())          # resolve_txt's working copy
    monkeypatch.setattr(txt_loader, "resolve_txt",
                        lambda *a, **k: (work, "export"))
    log = []
    loaded = []
    host = types.SimpleNamespace(
        _settings=settings, _runner=_SyncRunner(argyll),
        _log=types.SimpleNamespace(appendPlainText=log.append,
                                   clear=lambda: None,
                                   ensureCursorVisible=lambda: None),
        set_ti3_path=loaded.append,
        ti3_manually_loaded=types.SimpleNamespace(emit=lambda: None),
        _show_txt_import_error=lambda out: log.append("ERROR " + out))
    host._on_txt2ti3_done = types.MethodType(TabProfile._on_txt2ti3_done,
                                             host)
    TabProfile._import_i1profiler_txt(host, src)
    assert loaded == [work.parent / "export.ti3"], log
    assert _table(loaded[0]) == _point_twin_table(tmp_path, argyll,
                                                  spectral=True)
    assert work.read_bytes() == src.read_bytes()   # the working copy too
    assert _leftovers() == []


def test_doors_that_convert_through_the_shared_converter():
    """The Measure tab's import and the scanner-target import convert with
    `convert_i1profiler_measurement` (covered above); Another reading
    has no comma rule of its own any more."""
    from ui.tabs import tab_measure
    from ui.dialogs import scanin_target_dialog
    from workflow import reading_compare
    assert "convert_i1profiler_measurement(" in inspect.getsource(tab_measure)
    assert "convert_i1profiler_measurement(" in inspect.getsource(
        scanin_target_dialog.ScaninTargetDialog._execute_i1profiler)
    src = inspect.getsource(reading_compare)
    assert "_decimal_points" not in src and "_COMMA_NUMBER" not in src
    assert "convert_i1profiler_measurement(" in inspect.getsource(
        reading_compare._reading_from_cgats_text)


def test_another_reading_reads_a_comma_export_through_the_import(tmp_path):
    argyll = _argyll()
    from workflow.reading_compare import compare, load_reading
    point = _export(tmp_path / "p" / "export.txt", xyz=True, spectral=True)
    comma = _export(tmp_path / "c" / "export.txt", xyz=True, spectral=True,
                    comma=True)
    before = comma.read_bytes()
    a = load_reading(point, argyll_bin=argyll)
    b = load_reading(comma, argyll_bin=argyll)
    c = compare(a, b)
    assert c.n == ROWS and c.worst == 0.0
    assert comma.read_bytes() == before and _leftovers() == []


def _not_a_number(path: Path) -> Path:
    t = path.read_text(encoding="utf-8")
    d = t.index("BEGIN_DATA\n") + len("BEGIN_DATA\n")
    row_end = t.index("\n", d)
    cells = t[d:row_end].split("\t")
    cells[3] = "n/a"
    path.write_text(t[:d] + "\t".join(cells) + t[row_end:], encoding="utf-8")
    return path


def test_the_runner_doors_refuse_in_their_own_words_and_tidy_up(
        tmp_path, settings, qapp, monkeypatch):
    """A comma file with a value that is no number, through the two doors
    that run txt2ti3 themselves: refused, the temporary copy gone, and
    txt2ti3's line names the person's file, never the copy."""
    argyll = _argyll()
    settings.set("argyll_bin_path", argyll)
    from ui.dialogs.tools_dialogs import I1ProfilerToTi3Dialog
    src = _not_a_number(_export(tmp_path / "in" / "export.txt", comma=True,
                                lab=True))
    before = src.read_bytes()
    dlg = I1ProfilerToTi3Dialog(_SyncRunner(argyll), settings)
    try:
        dlg._pick_input_file = lambda *a, **k: src
        dlg._pick_txt()
        dlg._output._dir_edit.setText(str(tmp_path / "out"))
        dlg._execute()
        log = dlg._log.toPlainText()
    finally:
        dlg.deleteLater()
    assert "[ERROR]" in log and "has unexpected type" in log
    assert "chromiq-decimal-points" not in log
    assert not (tmp_path / "out" / "export.ti3").exists()

    from ui.tabs.tab_profile import TabProfile
    import ui.txt_loader as txt_loader
    work = tmp_path / "project" / "export.txt"
    work.parent.mkdir()
    work.write_bytes(before)
    monkeypatch.setattr(txt_loader, "resolve_txt",
                        lambda *a, **k: (work, "export"))
    shown = []
    host = types.SimpleNamespace(
        _settings=settings, _runner=_SyncRunner(argyll),
        _log=types.SimpleNamespace(appendPlainText=lambda _t: None,
                                   clear=lambda: None,
                                   ensureCursorVisible=lambda: None),
        set_ti3_path=lambda p: pytest.fail("a refused file was loaded"),
        ti3_manually_loaded=types.SimpleNamespace(emit=lambda: None),
        _show_txt_import_error=shown.append)
    host._on_txt2ti3_done = types.MethodType(TabProfile._on_txt2ti3_done,
                                             host)
    TabProfile._import_i1profiler_txt(host, src)
    assert shown and "has unexpected type" in shown[0]
    assert "chromiq-decimal-points" not in shown[0]
    assert src.read_bytes() == before and work.read_bytes() == before
    assert _leftovers() == []
