"""4.3.26: every ColorSpecification a CxF file of ChromIQ's names is defined
in that same file.

jctay (printerknowledge forum, 2026-11-07) checked ChromIQ's RGB .pxf against
the CxF3 schema and it failed: each ``<cc:ColorRGB>`` says
``ColorSpecification="Unknown"``, and the RGB file never wrote the
``<cc:ColorSpecificationCollection>`` that defines "Unknown". The schema
declares that attribute a key reference, so a file naming a specification it
does not define is not a valid CxF3 file. The CMYK files and the .pwxf/.txf
always carried the collection; X-Rite's own RGB patch sets (TC9.18 RGB,
TC2.83 RGB) carry it too.

This test needs no schema and no network: it reads every CxF file ChromIQ
writes (RGB, CMYK and CMYK+N .pxf, the shuffled copies, and the turned .txf)
and checks the rule the schema enforces, in plain Python.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from workflow.i1profiler_export import export_from_ti1

from tests.test_i1profiler_export import CMYK_TI1, CMYKOGV_TI1, RGB_TI1, _write

CC = "{http://colorexchangeformat.com/CxF3-core}"


def _references_and_definitions(path: Path) -> "tuple[set, set]":
    root = ET.parse(path).getroot()
    defined = {el.get("Id") for el in root.iter(f"{CC}ColorSpecification")}
    named = {el.get("ColorSpecification") for el in root.iter()
             if el.get("ColorSpecification") is not None}
    return named, defined


def _assert_all_defined(path: Path) -> None:
    named, defined = _references_and_definitions(path)
    assert named, f"{path.name} names no ColorSpecification at all"
    missing = named - defined
    assert not missing, (
        f"{path.name} names ColorSpecification {sorted(missing)} but defines "
        f"only {sorted(defined)}")
    # The collection sits inside <cc:Resources>, after the ObjectCollection,
    # where the CxF3 schema's sequence puts it.
    root = ET.parse(path).getroot()
    res = root.find(f"{CC}Resources")
    tags = [c.tag for c in res]
    assert tags.index(f"{CC}ColorSpecificationCollection") > tags.index(
        f"{CC}ObjectCollection")


@pytest.mark.parametrize("name,content", [
    ("rgb.ti1", RGB_TI1), ("cmyk.ti1", CMYK_TI1), ("cmykogv.ti1", CMYKOGV_TI1)])
def test_every_pxf_and_its_shuffled_copy_defines_what_it_names(
        tmp_path, name, content):
    _txt, pxf = export_from_ti1(_write(tmp_path, name, content), tmp_path,
                                also_shuffled=True, shuffle_seed=7)
    shuffled = tmp_path / "i1profiler-shuffled.pxf"
    assert shuffled.is_file()
    for f in (pxf, shuffled):
        _assert_all_defined(f)


def test_the_turned_txf_defines_what_it_names(tmp_path):
    from core.file_manager import exports_subdir
    from workflow import i1profiler_turned as T

    from tests.test_i1profiler_turned_export import _chart

    ti2 = _chart(tmp_path / "turned", "Turned", 350)
    res = T.write_turned_export(ti2, exports_subdir(ti2.parent), "Turned")
    assert not res.skipped, res.skipped
    txfs = [p for p in res.written if p.suffix == ".txf"]
    assert txfs
    for f in txfs:
        _assert_all_defined(f)


def test_the_cmyk_txt_and_pxf_hold_values_inside_0_to_100(tmp_path):
    """A hand-made CMYK patch set can carry -2.5 or 104; the chart prints 0 %
    and 100 %, the RGB exports already clamp, and now CMYK does too."""
    ti1 = CMYK_TI1.replace("1 0 69.8 0 0 50 50 50", "1 -2.5 69.8 104 0 50 50 50")
    txt, pxf = export_from_ti1(_write(tmp_path, "cmyk.ti1", ti1), tmp_path)
    row = next(line for line in txt.read_text(encoding="utf-8").splitlines()
               if line.startswith("1 "))
    assert row.split()[1:5] == ["0.0000", "69.8000", "100.0000", "0.0000"]
    text = pxf.read_text(encoding="utf-8")
    assert "<cc:Cyan>0</cc:Cyan>" in text
    assert "<cc:Yellow>100</cc:Yellow>" in text
    assert "-2.5" not in text and ">104<" not in text
