"""4.3.32 review of feature A: a second reading saved by i1Profiler as CGATS
text is read EXACTLY as the import reads it.

Found in review (2026-11-11): `reading_compare.load_reading` parsed every
non-CxF file directly, past the import's converter. A real i1Profiler CGATS
export (doug3236's public i400_M2.txt: SAMPLE_ID, SAMPLE_NAME, RGB, XYZ on
the 0..1 scale, L*a*b*, SPECTRAL_NM380..730) compared with its OWN import
gave an average ΔE00 of 45 instead of 0, because i1Profiler's XYZ on the
0..1 scale was read as 0..100; the spectral-only export ("i1Profiler CGATS
Spectral" without CIE columns) was refused as "holds no XYZ or L*a*b*
values"; a decimal-comma export (i1Profiler on a German system) raised a
ValueError that left the window without any answer.

The fixtures here are shaped like that real export, built from the suite's
own ET-8550 verification reading (never a tester's file): tab-separated,
i1Profiler's own column names, XYZ and spectra on the 0..1 scale.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M                  # noqa: E402
from workflow.reading_compare import (                          # noqa: E402
    ReadingsNotComparable, compare, load_reading, reading_from_ti3)

SRC = (Path(__file__).parent / "data" / "g_basti_et8550_run1_verify"
       / "ET8550_EpsPremSG_AdobeRGB_CM_Okt26-verify.ti3")


def _argyll() -> str:
    from tests.argyll_env import argyll_bin_dir, argyll_tool
    if argyll_tool("txt2ti3") is None or argyll_tool("spec2cie") is None:
        pytest.skip("ArgyllCMS txt2ti3 / spec2cie are not installed")
    return str(argyll_bin_dir())


def _rows():
    lines = SRC.read_text(encoding="utf-8").splitlines()
    f0 = lines.index("BEGIN_DATA_FORMAT")
    fields = lines[f0 + 1].split()
    d0 = lines.index("BEGIN_DATA")
    d1 = lines.index("END_DATA")
    return fields, [ln.split() for ln in lines[d0 + 1:d1]]


def _i1p_export(out: Path, *, xyz: bool = True, spectral: bool = True,
                comma: bool = False) -> Path:
    """The ET-8550 reading as i1Profiler's CGATS text export writes one."""
    fields, rows = _rows()
    fi = {f: i for i, f in enumerate(fields)}
    spec = [f for f in fields if f.startswith("SPEC_")]
    head = ["SAMPLE_ID", "SAMPLE_NAME", "RGB_R", "RGB_G", "RGB_B"]
    if xyz:
        head += ["XYZ_X", "XYZ_Y", "XYZ_Z"]
    if spectral:
        head += [f"SPECTRAL_NM{f[5:]}" for f in spec]
    body = []
    for r in rows:
        v = [r[fi["SAMPLE_ID"]], r[fi["SAMPLE_LOC"]].strip('"')]
        v += [f"{float(r[fi[f'RGB_{c}']]) * 2.55:.2f}" for c in "RGB"]
        if xyz:
            v += [f"{float(r[fi[f'XYZ_{c}']]) / 100:.6f}" for c in "XYZ"]
        if spectral:
            v += [f"{float(r[fi[f]]) / 100:.6f}" for f in spec]
        if comma:
            v = v[:2] + [x.replace(".", ",") for x in v[2:]]
        body.append("\t".join(v))
    text = ("CGATS.17\n\nORIGINATOR\t\"i1Profiler - X-Rite, Inc.\"\n"
            "INSTRUMENTATION\t\"i1Pro 3 ; Serial number 0\"\n"
            "MEASUREMENT_SOURCE\t\"MeasurementCondition=M2\tFilter=UVcut\"\n"
            "CREATED\t\"2026-11-11T20:00:00\"\n\n"
            f"NUMBER_OF_FIELDS\t{len(head)}\nBEGIN_DATA_FORMAT\n"
            + "\t".join(head) + "\nEND_DATA_FORMAT\n\n"
            f"NUMBER_OF_SETS\t{len(body)}\nBEGIN_DATA\n" + "\n".join(body)
            + "\nEND_DATA\n")
    out.write_text(text, encoding="utf-8")
    return out


@pytest.fixture
def first(tmp_path):
    return reading_from_ti3(SRC)


@pytest.mark.parametrize("kind", ["xyz-and-spectral", "spectral-only",
                                  "xyz-only", "decimal-comma"])
def test_an_i1profiler_cgats_export_compares_as_the_same_reading(
        first, tmp_path, monkeypatch, kind):
    argyll = _argyll()
    tmpd = tmp_path / "tmpd"
    tmpd.mkdir()
    import tempfile
    monkeypatch.setattr(tempfile, "tempdir", str(tmpd))
    kw = {"xyz-and-spectral": {}, "spectral-only": {"xyz": False},
          "xyz-only": {"spectral": False},
          "decimal-comma": {"comma": True}}[kind]
    src = _i1p_export(tmp_path / f"{kind}.txt", **kw)
    before = src.read_bytes()
    c = compare(first, load_reading(src, first.condition, argyll_bin=argyll))
    # the same readings: as near zero as rounding to six places allows
    assert c.n == 616 and c.paired_by == "id"
    assert c.mean < 0.05 and c.worst < 0.3, (c.mean, c.worst)
    assert src.read_bytes() == before
    assert list(tmpd.iterdir()) == []         # the temporary folder is gone


def test_a_value_that_is_not_a_number_is_refused_in_words(tmp_path):
    text = SRC.read_text(encoding="utf-8").splitlines()
    d0 = text.index("BEGIN_DATA")
    row = text[d0 + 1].split()
    row[5] = "n/a"
    text[d0 + 1] = " ".join(row)
    bad = tmp_path / "bad.ti3"
    bad.write_text("\n".join(text) + "\n", encoding="utf-8")
    with pytest.raises(ReadingsNotComparable) as e:
        load_reading(bad)
    assert e.value.message is M.M_READINGS_UNUSABLE


def test_a_file_argyll_cannot_convert_is_refused_in_words(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("CGATS.17\nBEGIN_DATA_FORMAT\nSAMPLE_ID\nEND_DATA_FORMAT\n"
                 "BEGIN_DATA\n1\nEND_DATA\n", encoding="utf-8")
    with pytest.raises(ReadingsNotComparable) as e:
        load_reading(p, argyll_bin=str(tmp_path / "no-argyll-here"))
    assert e.value.message is M.M_READINGS_UNUSABLE
