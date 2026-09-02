"""Imported i1Profiler measurements feed the Measurement Report self-contained
(Knut): no .ti2 needed (expected colour derived from device RGB), 0..255 device
scale handled, and the instrument stamped from the export's INSTRUMENTATION tag.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from workflow.measurement_report import build_report
from workflow.reference_convert import (
    read_instrumentation, read_measurement_date, stamp_instrument_from_source,
    stamp_measurement_date_from_source, finalize_converted_ti3,
)

# An i1Profiler-style measurement .ti3 (as txt2ti3 would produce): device RGB on
# the 0..255 code-value scale, no sibling .ti2. Measured XYZ are D50 (as a real
# .ti3 is): white and black sit on their D50 sRGB reference (near-zero ΔE); the
# red patch is measured off, so it's the worst.
_TI3_255 = """CTI3

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 3
BEGIN_DATA
1 "A1" 255 255 255 96.42 100.0 82.53
2 "A2" 0 0 0 0.96 1.0 0.83
3 "A3" 255 0 0 36.0 18.0 3.0
END_DATA
"""


def test_report_self_contained_from_255_device_rgb(tmp_path: Path):
    (tmp_path / "chart.ti3").write_text(_TI3_255, encoding="utf-8")
    r = build_report(tmp_path / "chart.ti3")
    # No .ti2 → device-derived reference, full ΔE available.
    assert r["reference_source"] == "device"
    assert r["de00"]["n"] == 3
    # 0..255 normalised → corner detection still finds white/black/red patches.
    by = {c["name"]: c for c in r["corners"]}
    assert by["W"]["loc"] == "A1" and by["K"]["loc"] == "A2" and by["R"]["loc"] == "A3"
    # White measured at its sRGB estimate → near-zero ΔE; red is the worst.
    assert r["worst_patches"][0]["loc"] == "A3"
    assert by["W"]["de"] < 1.0


def _measurement_txt(tmp_path: Path, instr: str) -> Path:
    p = tmp_path / "m.txt"
    p.write_text(f'CGATS.5\n\nINSTRUMENTATION "{instr}"\n\n'
                 "BEGIN_DATA_FORMAT\nSampleID RGB_R RGB_G RGB_B\n"
                 "END_DATA_FORMAT\nBEGIN_DATA\n1 255 255 255\nEND_DATA\n", encoding="utf-8")
    return p


def test_read_instrumentation(tmp_path: Path):
    assert read_instrumentation(_measurement_txt(tmp_path, "i1Pro 2")) == "i1Pro 2"
    assert read_instrumentation(_measurement_txt(tmp_path, "Not specified")) is None
    assert read_instrumentation(_measurement_txt(tmp_path, "")) is None


def test_stamp_instrument_from_source_uses_real_name(tmp_path: Path):
    src = _measurement_txt(tmp_path, "i1iSis")
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text(_TI3_255, encoding="utf-8")
    got = stamp_instrument_from_source(ti3, src)
    assert got == "i1iSis"
    assert 'TARGET_INSTRUMENT "i1iSis"' in ti3.read_text(encoding="utf-8")
    # The report now shows the real instrument.
    assert build_report(ti3)["instrument"] == "i1iSis"


def test_stamp_instrument_falls_back_when_unspecified(tmp_path: Path):
    src = _measurement_txt(tmp_path, "Not specified")
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text(_TI3_255, encoding="utf-8")
    got = stamp_instrument_from_source(ti3, src)
    assert got == "i1Profiler (unspecified)"
    assert build_report(ti3)["instrument"] == "i1Profiler (unspecified)"


def test_stamp_instrument_no_op_when_already_present(tmp_path: Path):
    src = _measurement_txt(tmp_path, "i1Pro 2")
    ti3 = tmp_path / "chart.ti3"
    # A genuine chartread file already names its instrument — don't overwrite.
    ti3.write_text(_TI3_255.replace(
        "NUMBER_OF_FIELDS 7",
        'KEYWORD "TARGET_INSTRUMENT"\nTARGET_INSTRUMENT "i1Pro 3"\n\n'
        "NUMBER_OF_FIELDS 7"), encoding="utf-8")
    got = stamp_instrument_from_source(ti3, src)
    assert got == "i1Pro 3"
    assert 'TARGET_INSTRUMENT "i1Pro 2"' not in ti3.read_text(encoding="utf-8")


def test_stamp_instrument_overrides_txt2ti3_placeholder(tmp_path: Path):
    # txt2ti3 always hard-codes TARGET_INSTRUMENT "GretagMacbeth Spectrolino" — that's a
    # placeholder, not the real instrument, so it must be replaced with the one
    # named in the source file (Knut).
    src = _measurement_txt(tmp_path, "i1iSis")
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text(_TI3_255.replace(
        "NUMBER_OF_FIELDS 7",
        'KEYWORD "TARGET_INSTRUMENT"\nTARGET_INSTRUMENT "GretagMacbeth Spectrolino"\n\n'
        "NUMBER_OF_FIELDS 7"), encoding="utf-8")
    got = stamp_instrument_from_source(ti3, src)
    assert got == "i1iSis"
    text = ti3.read_text(encoding="utf-8")
    assert 'TARGET_INSTRUMENT "i1iSis"' in text
    assert "spectrolino" not in text.lower()
    assert build_report(ti3)["instrument"] == "i1iSis"


def _dated_txt(tmp_path: Path, created: str, instr: str = "i1iSis") -> Path:
    p = tmp_path / "m.txt"
    p.write_text(f'CGATS.17\n\nINSTRUMENTATION "{instr}"\nCREATED "{created}"\n\n'
                 "BEGIN_DATA_FORMAT\nSampleID RGB_R RGB_G RGB_B\n"
                 "END_DATA_FORMAT\nBEGIN_DATA\n1 255 255 255\nEND_DATA\n", encoding="utf-8")
    return p


def test_read_measurement_date_is_locale_safe(tmp_path: Path):
    # English month names must parse regardless of the process locale (not via
    # strptime %B, which is locale-dependent), plus ISO / numeric forms.
    cases = {
        "January 06, 2026": "2026-01-06", "Jul 4 2026": "2026-07-04",
        "2026-03-15": "2026-03-15", "03/15/2026": "2026-03-15",
        "15.03.2026": "2026-03-15", "Tue Jul 21 00:44:31 2026": "2026-07-21",
    }
    for raw, iso in cases.items():
        assert read_measurement_date(_dated_txt(tmp_path, raw)) == iso, raw
    # A locale switch must not break the English-month parse.
    import locale
    try:
        locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")
    except locale.Error:
        pass
    try:
        assert read_measurement_date(_dated_txt(tmp_path, "January 06, 2026")) == "2026-01-06"
    finally:
        locale.setlocale(locale.LC_TIME, "C")


def test_stamp_and_report_use_measurement_date(tmp_path: Path):
    src = _dated_txt(tmp_path, "January 06, 2026")
    ti3 = tmp_path / "chart.ti3"; ti3.write_text(_TI3_255, encoding="utf-8")
    assert stamp_measurement_date_from_source(ti3, src) == "2026-01-06"
    assert 'CHROMIQ_MEASURED "2026-01-06"' in ti3.read_text(encoding="utf-8")
    # the report dates the run by the measurement date, not "now"
    assert build_report(ti3)["created"].startswith("2026-01-06")


def test_finalize_stamps_both_instrument_and_date(tmp_path: Path):
    src = _dated_txt(tmp_path, "March 15, 2026", instr="i1Pro 2")
    ti3 = tmp_path / "chart.ti3"; ti3.write_text(_TI3_255, encoding="utf-8")
    instr, date = finalize_converted_ti3(ti3, src)
    assert instr == "i1Pro 2" and date == "2026-03-15"
    rep = build_report(ti3)
    assert rep["instrument"] == "i1Pro 2" and rep["created"].startswith("2026-03-15")


def test_report_without_measurement_date_uses_now(tmp_path: Path):
    # A native chartread .ti3 (no CHROMIQ_MEASURED) still dates by build time.
    ti3 = tmp_path / "chart.ti3"; ti3.write_text(_TI3_255, encoding="utf-8")
    from datetime import date as _date
    assert build_report(ti3)["created"].startswith(_date.today().isoformat())


def test_stamp_instrument_placeholder_falls_back(tmp_path: Path):
    # txt2ti3 placeholder + a source that names no instrument → clear fallback.
    src = _measurement_txt(tmp_path, "Not specified")
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text(_TI3_255.replace(
        "NUMBER_OF_FIELDS 7",
        'KEYWORD "TARGET_INSTRUMENT"\nTARGET_INSTRUMENT "GretagMacbeth Spectrolino"\n\n'
        "NUMBER_OF_FIELDS 7"), encoding="utf-8")
    got = stamp_instrument_from_source(ti3, src)
    assert got == "i1Profiler (unspecified)"
    assert "spectrolino" not in ti3.read_text(encoding="utf-8").lower()
