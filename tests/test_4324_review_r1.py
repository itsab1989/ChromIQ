"""4.3.24, review round 1 of the i1Profiler / XYZ branch (L2, L4, L5, L6).

* L2: a merge or average of measurements whose XYZ was computed in
  different ways (``CHROMIQ_XYZ_METHOD``) does not claim the new method.
* L4: the CIE tables are named in THIRD-PARTY-NOTICES.md.
* L5: spectra with fewer than 4 wavelengths are refused, never computed
  differently from ArgyllCMS.
* L6: only "0", "1", "2" are i1Profiler's numbers; a one-condition file whose
  saved choice is another says so; a value that is not a number is refused.

Every fixture is invented.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_4324_cxf_selected_condition import _native            # noqa: E402
from workflow import measurement_messages as M                       # noqa: E402
from workflow.argyll_colorimetry import spectra_to_xyz_like_argyll     # noqa: E402
from workflow.measurement_condition import read_header_keyword        # noqa: E402
from workflow.reference_convert import (                               # noqa: E402
    XYZ_METHOD_KEYWORD, ReferenceConvertError, condition_from_label,
    cxf_measurement_to_ti3)
from workflow.ti3_merge import settle_combined_xyz_method              # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


# ---- L6 -----------------------------------------------------------------------

@pytest.mark.parametrize("value", ["-0", "00", "+1", "01", "+2", "-1"])
def test_only_i1profilers_own_spellings_are_its_numbers(value):
    assert condition_from_label(value) is None


def test_a_one_condition_file_whose_saved_choice_is_another_says_so(
        qapp, tmp_path):
    from ui.dialogs.cxf_condition_dialog import choose_cxf_condition
    log = []
    got = choose_cxf_condition(None, _native(tmp_path / "a.mxf", ("M1",), "2"),
                               log=log.append)
    assert got == "M1"
    assert log == [M.cxf_condition_log_line("M1", ("M1",), "M2")]
    assert "M2" in log[0] and "the only one" in log[0]
    # …and the ordinary case keeps its line
    log.clear()
    choose_cxf_condition(None, _native(tmp_path / "b.mxf", ("M1",), "1"),
                         log=log.append)
    assert log == [M.cxf_condition_log_line("M1", ("M1",))]


def _with_spectrum(path: Path, patch: int, values) -> Path:
    """*path* with the spectrum of the *patch*-th reading replaced."""
    text = path.read_text(encoding="utf-8")
    spans = list(re.finditer(
        r'(<cc:ReflectanceSpectrum [^>]*>)([^<]*)(</cc:ReflectanceSpectrum>)',
        text))
    m = spans[patch - 1]
    text = (text[:m.start(2)] + " ".join(values) + text[m.end(2):])
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize("bad", ["nan", "NaN", "inf", "-INF", "abc"])
def test_a_value_that_is_not_a_number_is_refused_and_named(tmp_path, bad):
    src = _native(tmp_path / "a.mxf", ("M1",), "1")
    vals = ["0.5"] * 36
    vals[7] = bad
    _with_spectrum(src, 3, vals)
    out = tmp_path / "a.ti3"
    with pytest.raises(ReferenceConvertError) as e:
        cxf_measurement_to_ti3(src, out)
    assert e.value.message_id == "M-CONVERT-CXF-SPECTRUM-NOT-A-NUMBER"
    text = str(e.value)
    # what the file calls it (the reading's Name), and its place (review r2, N3)
    assert "“M1_Measurement3”" in text and "3 of 12" in text
    assert f"“{bad}”" in text
    assert not out.exists(), "nothing may be written"


def test_a_patch_with_a_sample_name_is_named_by_it(tmp_path):
    """SampleName first, then the reading's Name, then its place (N3)."""
    src = _native(tmp_path / "a.mxf", ("M1",), "1")
    text = src.read_text(encoding="utf-8")
    # give the second reading a SampleName, as some writers do
    parts = text.split("</cc:ColorValues>")
    parts[2] = ('<cc:TagCollection Name="Location"><cc:Tag Name="SampleName" '
                'Value="A12"/></cc:TagCollection>') + parts[2]
    src.write_text("</cc:ColorValues>".join(parts), encoding="utf-8")
    vals = ["0.5"] * 36
    vals[0] = "nan"
    _with_spectrum(src, 2, vals)
    with pytest.raises(ReferenceConvertError) as e:
        cxf_measurement_to_ti3(src, tmp_path / "a.ti3")
    assert "“A12”" in str(e.value)
    assert M.M_CONVERT_CXF_SPECTRUM_NOT_A_NUMBER.render(
        name="a.mxf", patch="A12", index=2, count=12, value="nan")[1] \
        == str(e.value)


# ---- L5 -----------------------------------------------------------------------

def test_fewer_than_four_wavelengths_are_refused(tmp_path):
    with pytest.raises(ValueError, match="at least 4"):
        spectra_to_xyz_like_argyll(np.ones((1, 3)), [400.0, 500.0, 600.0])
    src = _native(tmp_path / "a.mxf", ("M1",), "1")
    text = src.read_text(encoding="utf-8")
    text = re.sub(r'(<cc:ReflectanceSpectrum [^>]*>)[^<]*(<)',
                  r'\g<1>0.5 0.6 0.7\g<2>', text)
    src.write_text(text, encoding="utf-8")
    with pytest.raises(ReferenceConvertError) as e:
        cxf_measurement_to_ti3(src, tmp_path / "a.ti3")
    assert e.value.message_id == "M-CONVERT-CXF-TOO-FEW-BANDS"
    assert "3" in str(e.value)


def _three_band_ti3(path: Path, *, with_xyz: bool) -> Path:
    """A .ti3 with 3-band spectra (450/550/650 nm); no instrument writes
    one, 4.3.23 read it (review r2, N1)."""
    fields = "SAMPLE_ID RGB_R RGB_G RGB_B " + (
        "XYZ_X XYZ_Y XYZ_Z " if with_xyz else "") + "SPEC_450 SPEC_550 SPEC_650"
    rows = []
    for i, (r, y) in enumerate([(100, 90.0), (0, 3.0), (50, 40.0), (75, 60.0)],
                               1):
        xyz = f"{y * 0.96:.3f} {y:.3f} {y * 0.82:.3f} " if with_xyz else ""
        rows.append(f"{i} {r} {r} {r} {xyz}{y:.2f} {y:.2f} {y:.2f}")
    n = len(fields.split())
    path.write_text("\n".join([
        "CTI3", "", 'DESCRIPTOR "three bands"', 'ORIGINATOR "test"',
        'DEVICE_CLASS "OUTPUT"', 'COLOR_REP "RGB_XYZ"',
        'SPECTRAL_BANDS "3"', 'SPECTRAL_START_NM "450.000000"',
        'SPECTRAL_END_NM "650.000000"', "", f"NUMBER_OF_FIELDS {n}",
        "BEGIN_DATA_FORMAT", fields, "END_DATA_FORMAT", "",
        f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA", *rows, "END_DATA", ""]),
        encoding="utf-8")
    return path


def test_three_bands_with_xyz_are_analysed_as_before(tmp_path):
    from workflow.ti3_analysis import analyse_ti3, parse_ti3
    data = parse_ti3(_three_band_ti3(tmp_path / "a.ti3", with_xyz=True))
    assert data.spectral is None           # the spectral part is left out
    res = analyse_ti3(data)
    assert res.illuminant_points == []
    assert np.allclose(np.asarray(data.xyz)[0], [86.4, 90.0, 73.8])


def test_three_bands_without_xyz_say_why_they_cannot_be_read(tmp_path):
    from workflow.ti3_analysis import Ti3ParseError, parse_ti3
    with pytest.raises(Ti3ParseError, match="fewer than 4 wavelengths"):
        parse_ti3(_three_band_ti3(tmp_path / "a.ti3", with_xyz=False))


def test_the_info_window_shows_a_three_band_file(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    dlg = Ti3InfoDialog(ArgyllRunner(s), s)
    dlg.load_measurement(_three_band_ti3(tmp_path / "a.ti3", with_xyz=True))
    assert dlg._report, "the window shows nothing"
    # a spectral-only one is refused by the window's own parse-error path
    dlg.load_measurement(_three_band_ti3(tmp_path / "b.ti3", with_xyz=False))
    dlg.deleteLater()


def test_the_engine_refuses_three_bands_with_its_own_error():
    from workflow.argyll_colorimetry import ColorimetryError
    from workflow.profile_engine.spectral import SpectralError, spectra_to_xyz
    with pytest.raises(SpectralError):
        spectra_to_xyz(np.full((1, 3), 50.0), np.array([450.0, 550.0, 650.0]))
    assert issubclass(ColorimetryError, ValueError)


def test_four_wavelengths_still_work():
    xyz = spectra_to_xyz_like_argyll(np.full((1, 4), 100.0),
                                     [400.0, 500.0, 600.0, 700.0],
                                     percent=True)
    assert xyz[0][1] == pytest.approx(100.0, abs=1e-9)


# ---- L2 -----------------------------------------------------------------------

def _with_method(src: Path, dst: Path, method: "str | None") -> Path:
    """A copy of the import *src* as an older import would be: without the
    method line (None), or with another value."""
    text = src.read_text(encoding="utf-8")
    text = re.sub(rf'KEYWORD "{XYZ_METHOD_KEYWORD}"\n{XYZ_METHOD_KEYWORD} "[^"]*"\n',
                  "" if method is None else
                  f'KEYWORD "{XYZ_METHOD_KEYWORD}"\n{XYZ_METHOD_KEYWORD} "{method}"\n',
                  text)
    dst.write_text(text, encoding="utf-8")
    return dst


@pytest.fixture
def two_imports(tmp_path):
    new = cxf_measurement_to_ti3(_native(tmp_path / "n.mxf", ("M1",), "1"),
                                 tmp_path / "new.ti3")
    old = _with_method(new, tmp_path / "old.ti3", None)
    assert read_header_keyword(new, XYZ_METHOD_KEYWORD)
    assert read_header_keyword(old, XYZ_METHOD_KEYWORD) is None
    return new, old


def test_a_result_of_inputs_that_disagree_names_no_method(tmp_path,
                                                          two_imports):
    new, old = two_imports
    result = shutil.copy(new, tmp_path / "result.ti3")   # average copies #1
    before = Path(result).read_text(encoding="utf-8")
    settle_combined_xyz_method(Path(result), [new, old])
    after = Path(result).read_text(encoding="utf-8")
    assert read_header_keyword(result, XYZ_METHOD_KEYWORD) is None
    assert after.split("BEGIN_DATA_FORMAT")[1] == \
        before.split("BEGIN_DATA_FORMAT")[1], "only the header may change"
    # a different value disagrees too
    other = _with_method(new, tmp_path / "other.ti3", "something else")
    result = shutil.copy(new, tmp_path / "result2.ti3")
    settle_combined_xyz_method(Path(result), [new, other])
    assert read_header_keyword(result, XYZ_METHOD_KEYWORD) is None


def test_a_result_of_inputs_that_agree_keeps_it(tmp_path, two_imports):
    new, _old = two_imports
    new2 = shutil.copy(new, tmp_path / "new2.ti3")
    result = shutil.copy(new, tmp_path / "result.ti3")
    settle_combined_xyz_method(Path(result), [new, Path(new2)])
    assert read_header_keyword(result, XYZ_METHOD_KEYWORD) == \
        read_header_keyword(new, XYZ_METHOD_KEYWORD)


def test_settling_the_condition_settles_the_method_too(tmp_path, two_imports):
    """The Measure tab's and the Tools averaging call only this."""
    from workflow.ti3_merge import condition_check, settle_combined_condition
    new, old = two_imports
    result = Path(shutil.copy(new, tmp_path / "result.ti3"))
    settle_combined_condition(result, condition_check([new, old]),
                              confirmed=True)
    assert read_header_keyword(result, XYZ_METHOD_KEYWORD) is None
    assert read_header_keyword(result, "MEASUREMENT_CONDITION") == "M1"


def _average() -> "str | None":
    p = Path("/Applications/Argyll/bin/average")
    return str(p) if p.exists() else shutil.which("average")


@pytest.mark.skipif(not _average(), reason="ArgyllCMS not installed")
def test_a_real_merge_of_an_old_and_a_new_import(tmp_path, two_imports):
    from workflow.ti3_merge import merge_measurements
    new, old = two_imports
    out = tmp_path / "merged.ti3"
    merge_measurements([new, old], out, Path(_average()).parent)
    assert out.exists()
    assert read_header_keyword(out, XYZ_METHOD_KEYWORD) is None
    out2 = tmp_path / "merged2.ti3"
    new2 = Path(shutil.copy(new, tmp_path / "new2.ti3"))
    merge_measurements([new, new2], out2, Path(_average()).parent)
    assert read_header_keyword(out2, XYZ_METHOD_KEYWORD)


# ---- L4 -----------------------------------------------------------------------

def test_the_cie_tables_are_named_in_the_notices():
    text = (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    assert "workflow/cie_data.py" in text
    assert "workflow/profile_engine/spectral_data.py" in text
    assert "CIE standard data" in text
    src = (ROOT / "workflow" / "argyll_colorimetry.py").read_text(
        encoding="utf-8")
    assert "The tables are ArgyllCMS's own" not in src
