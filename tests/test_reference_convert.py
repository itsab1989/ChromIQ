"""Auto-conversion of manufacturer target references (Knut #3).

Detection is content-based; the actual Argyll runs are driven through an
injected runner so the pipeline (which tool, in what order, producing which
file) is verified without the .cxf/spectral sample files or the binaries."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from workflow.reference_convert import (
    ReferenceConvertError, ReferenceKind, classify_reference, convert_reference,
    needs_conversion)


def _cgats_xyz(path: Path) -> Path:
    path.write_text("IT8.7/2\nBEGIN_DATA_FORMAT\nSAMPLE_ID XYZ_X XYZ_Y XYZ_Z\n"
                    "END_DATA_FORMAT\nBEGIN_DATA\nA1 3 2 1\nEND_DATA\n", encoding="utf-8")
    return path


def test_classify(tmp_path):
    assert classify_reference(_cgats_xyz(tmp_path / "wolf.txt")) is ReferenceKind.DIRECT
    (tmp_path / "r.cie").write_text("x", encoding="utf-8"); assert classify_reference(tmp_path / "r.cie") is ReferenceKind.DIRECT
    (tmp_path / "r.cxf").write_text("<CxF/>", encoding="utf-8"); assert classify_reference(tmp_path / "r.cxf") is ReferenceKind.CXF
    spec = tmp_path / "spectral.txt"
    spec.write_text("SAMPLE_NAME nm400 nm410 nm420\nP1 0.1 0.2 0.3\n", encoding="utf-8")
    assert classify_reference(spec) is ReferenceKind.SPECTRAL_TXT
    assert needs_conversion(spec) and not needs_conversion(tmp_path / "wolf.txt")


class _FakeArgyll:
    """Creates a fake bin dir with the converter exes, and a runner that records
    calls and fabricates each tool's output file."""
    def __init__(self, tmp_path):
        self.bin = tmp_path / "bin"; self.bin.mkdir()
        for t in ("cxf2ti3", "txt2ti3", "spec2cie"):
            (self.bin / t).write_text("#!/bin/sh\n", encoding="utf-8")
        self.calls = []

    def run(self, cmd, capture_output=True, text=True):
        self.calls.append(cmd)
        tool = Path(cmd[0]).name
        if tool == "cxf2ti3":
            Path(cmd[2] + ".ti3").write_text("cie", encoding="utf-8")            # outbase.ti3
        elif tool == "txt2ti3":
            Path(cmd[2] + ".ti3").write_text("spectral ti3", encoding="utf-8")   # tmpbase.ti3
        elif tool == "spec2cie":
            Path(cmd[2]).write_text("cie with xyz", encoding="utf-8")            # out.cie
        return subprocess.CompletedProcess(cmd, 0, "", "")


def test_direct_returned_unchanged(tmp_path):
    ref = _cgats_xyz(tmp_path / "wolf.txt")
    fk = _FakeArgyll(tmp_path)
    out = convert_reference(ref, fk.bin, tmp_path / "out", runner=fk.run)
    assert out == ref and not fk.calls        # no conversion, no tools run


def test_cxf_runs_cxf2ti3(tmp_path):
    ref = tmp_path / "R250715.cxf"; ref.write_text("<CxF/>", encoding="utf-8")
    fk = _FakeArgyll(tmp_path)
    out = convert_reference(ref, fk.bin, tmp_path / "out", runner=fk.run)
    assert out.suffix == ".ti3" and out.is_file()
    assert [Path(c[0]).name for c in fk.calls] == ["cxf2ti3"]


def test_spectral_txt_runs_txt2ti3_then_spec2cie(tmp_path):
    ref = tmp_path / "DT7.txt"
    ref.write_text("SAMPLE_NAME nm400 nm410\nP1 0.1 0.2\n", encoding="utf-8")
    fk = _FakeArgyll(tmp_path)
    out = convert_reference(ref, fk.bin, tmp_path / "out", runner=fk.run)
    assert out.suffix == ".cie" and out.is_file()
    assert [Path(c[0]).name for c in fk.calls] == ["txt2ti3", "spec2cie"]


def test_missing_tool_raises(tmp_path):
    ref = tmp_path / "r.cxf"; ref.write_text("<CxF/>", encoding="utf-8")
    with pytest.raises(ReferenceConvertError):
        convert_reference(ref, tmp_path / "empty_bin", tmp_path / "out")


def test_converter_failure_raises(tmp_path):
    ref = tmp_path / "r.cxf"; ref.write_text("<CxF/>", encoding="utf-8")
    fk = _FakeArgyll(tmp_path)
    def boom(cmd, **k): return subprocess.CompletedProcess(cmd, 1, "", "bad file")
    with pytest.raises(ReferenceConvertError):
        convert_reference(ref, fk.bin, tmp_path / "out", runner=boom)


def test_i1profiler_measurement_ti3_passthrough(tmp_path):
    from workflow.reference_convert import convert_i1profiler_measurement
    t3 = tmp_path / "m.ti3"; t3.write_text("CTI3\n", encoding="utf-8")
    fk = _FakeArgyll(tmp_path)
    # A .ti3 is already usable — returned unchanged, no tool run.
    assert convert_i1profiler_measurement(t3, fk.bin, tmp_path / "out",
                                          runner=fk.run) == t3
    assert not fk.calls


def test_i1profiler_measurement_txt_converted(tmp_path):
    from workflow.reference_convert import convert_i1profiler_measurement
    txt = tmp_path / "meas.txt"; txt.write_text("SAMPLE_ID ...\n", encoding="utf-8")
    fk = _FakeArgyll(tmp_path)
    out = convert_i1profiler_measurement(txt, fk.bin, tmp_path / "out",
                                         runner=fk.run)
    assert out.name == "meas.ti3" and out.is_file()
    assert [Path(c[0]).name for c in fk.calls] == ["txt2ti3"]
