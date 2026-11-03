"""i1Profiler NATIVE measurement import: CxF3 (.mxf/.cxf) → .ti3 directly, no
txt2ti3, no export step (Knut/Basti). Instrument (MeasurementDevice) and date
(CreationDate) are stamped; device RGB rescaled 0..255 → 0..100; reflectance →
XYZ; the result reads self-contained in the report."""
from __future__ import annotations

from pathlib import Path

import pytest

from workflow.reference_convert import (
    is_cxf, cxf_measurement_to_ti3, convert_i1profiler_measurement,
    ReferenceConvertError,
)
from workflow.ti3_analysis import parse_ti3
from workflow.measurement_report import build_report

_NS = "http://colorexchangeformat.com/CxF3-core"
# 36-band (380..730/10 nm) reflectances for white / black / red-ish.
_SPECTRA = {
    "white": [0.82] * 36,
    "black": [0.03] * 36,
    "red":   [0.05] * 18 + [0.55] * 18,
}
_RGB = {"white": (255, 255, 255), "black": (0, 0, 0), "red": (255, 0, 0)}


def _cxf(tmp_path: Path, *, device_attr=True, created="2026-02-14T10:00:00Z",
         ext=".mxf") -> Path:
    def obj_target(i, name):
        r, g, b = _RGB[name]
        return (f'<cc:Object ObjectType="Target" Name="Target{i}" Id="t{i}">'
                f'<cc:DeviceColorValues><cc:ColorRGB ColorSpecification="Unknown">'
                f'<cc:R>{r}</cc:R><cc:G>{g}</cc:G><cc:B>{b}</cc:B></cc:ColorRGB>'
                f'</cc:DeviceColorValues></cc:Object>')

    def obj_meas(i, name):
        s = " ".join(f"{v}" for v in _SPECTRA[name])
        return (f'<cc:Object ObjectType="M2_Measurement" Name="M2_Measurement{i}" '
                f'Id="m{i}"><cc:CreationDate>{created}</cc:CreationDate>'
                f'<cc:ColorValues><cc:ReflectanceSpectrum StartWL="380">{s}'
                f'</cc:ReflectanceSpectrum></cc:ColorValues></cc:Object>')

    names = ["white", "black", "red"]
    dev = ' MeasurementDevice="i1Pro 2"' if device_attr else ""
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<cc:CxF xmlns:cc="{_NS}">'
           f'<cc:FileInformation><cc:CreationDate>{created}</cc:CreationDate>'
           f'</cc:FileInformation>'
           f'<cc:Resources><cc:ObjectCollection>'
           + "".join(obj_target(i + 1, n) for i, n in enumerate(names))
           + "".join(obj_meas(i + 1, n) for i, n in enumerate(names))
           + f'</cc:ObjectCollection>'
           f'<cc:CustomResources><cc:MeasurementSpecification{dev}/>'
           f'</cc:CustomResources></cc:Resources></cc:CxF>')
    p = tmp_path / f"meas{ext}"
    p.write_text(xml, encoding="utf-8")
    return p


def test_is_cxf():
    assert is_cxf("x.mxf") and is_cxf("X.CXF") and not is_cxf("x.txt")


def test_cxf_to_ti3_stamps_instrument_date_and_rescales(tmp_path: Path):
    out = cxf_measurement_to_ti3(_cxf(tmp_path), tmp_path / "out.ti3")
    d = parse_ti3(out)
    assert len(d.sample_ids) == 3
    # ArgyllCMS's name for it since 4.3.23, i1Profiler's own kept beside it.
    assert d.keywords.get("TARGET_INSTRUMENT") == "X-Rite i1 Pro 2"
    assert d.keywords.get("CHROMIQ_I1P_INSTRUMENT") == "i1Pro 2"
    assert d.keywords.get("CHROMIQ_MEASURED") == "2026-02-14"
    import numpy as np
    assert float(np.asarray(d.rgb).max()) <= 100.5      # 0..255 → 0..100
    # white patch is the lightest measured
    rep = build_report(out)
    assert rep["reference_source"] == "device"
    assert rep["created"].startswith("2026-02-14")
    assert rep["instrument"] == "X-Rite i1 Pro 2"
    assert rep["paper_white"]["lab"][0] > rep["max_black"]["lab"][0]


def test_cxf_without_device_attr_falls_back(tmp_path: Path):
    out = cxf_measurement_to_ti3(_cxf(tmp_path, device_attr=False), tmp_path / "o.ti3")
    assert parse_ti3(out).keywords.get("TARGET_INSTRUMENT") == "i1Profiler (unspecified)"


def test_convert_dispatcher_routes_cxf(tmp_path: Path):
    # convert_i1profiler_measurement dispatches .mxf/.cxf to the CxF path (no
    # txt2ti3 / no runner needed).
    src = _cxf(tmp_path, ext=".cxf")
    out = convert_i1profiler_measurement(src, "/nonexistent/argyll", tmp_path / "d")
    assert out.suffix == ".ti3" and out.is_file()
    assert parse_ti3(out).keywords.get("TARGET_INSTRUMENT") == "X-Rite i1 Pro 2"


def test_cxf_rejects_mismatched_or_empty(tmp_path: Path):
    bad = tmp_path / "bad.mxf"
    bad.write_text(f'<cc:CxF xmlns:cc="{_NS}"><cc:Resources><cc:ObjectCollection>'
                   f'</cc:ObjectCollection></cc:Resources></cc:CxF>', encoding="utf-8")
    with pytest.raises(ReferenceConvertError):
        cxf_measurement_to_ti3(bad, tmp_path / "o.ti3")
