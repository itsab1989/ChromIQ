"""The i1Profiler patch set (``-i1profiler.pxf``) names the device.

The coordinator, 2026-11-14, from an i1iO owner's files: `write_pxf` wrote
``MeasurementDevice="i1iSis"`` for EVERY chart. Now an i1iSis chart (its Beta
on) names the device i1Profiler itself writes for it ("i1iSis", or "i1iSis XL"
for the XL models: X-Rite's own default-i1iSis.txf), and an i1iO chart (its
Beta on) "i1iO 2", the name in i1Profiler's own shipped i1iO 2 charts
("TC1617x (i1iO2).txf"). Every other chart keeps the long-standing value, so
its file is byte for byte what it was (`workflow.chart_exports.
i1profiler_device_for` answers None and `write_pxf` keeps its default)."""
from __future__ import annotations

import pytest

from workflow.chart_exports import i1profiler_device_for


def _chart(tmp_path, name, extra=""):
    ti2 = tmp_path / "c.ti2"
    ti2.write_text(
        "CTI2\n\n"
        f'TARGET_INSTRUMENT "{name}"\n{extra}COLOR_REP "RGB"\n'
        "NUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B\n"
        "END_DATA_FORMAT\nNUMBER_OF_SETS 1\nBEGIN_DATA\n"
        '1 "A1" 100 100 100\nEND_DATA\n', encoding="utf-8")
    return tmp_path / "c.ti1"


@pytest.fixture
def betas():
    from workflow.i1io import support as io
    from workflow.isis import support as isis
    before = (io._latched, isis._latched)

    def set_(on_io, on_isis):
        io.set_enabled_for_this_process(on_io)
        isis.set_enabled_for_this_process(on_isis)
    yield set_
    io._latched, isis._latched = before


@pytest.mark.parametrize("name", ["GretagMacbeth i1 Pro", "X-Rite ColorMunki",
                                  "GretagMacbeth SpectroScan", "CR30"])
def test_every_other_chart_keeps_the_default(tmp_path, betas, name):
    betas(True, True)
    assert i1profiler_device_for(_chart(tmp_path, name)) is None


def test_an_i1isis_chart_names_its_model(tmp_path, betas):
    import json
    betas(False, True)
    ti1 = _chart(tmp_path, "X-Rite i1iSis")
    assert i1profiler_device_for(ti1) == "i1iSis"
    (tmp_path / "c.isis.json").write_text(json.dumps({"model": "xl"}),
                                          encoding="utf-8")
    assert i1profiler_device_for(ti1) == "i1iSis XL"
    betas(False, False)
    assert i1profiler_device_for(ti1) is None


def test_an_i1io_chart_names_the_i1io_2(tmp_path, betas):
    betas(True, False)
    ti1 = _chart(tmp_path, "X-Rite i1iO")
    assert i1profiler_device_for(ti1) == "i1iO 2"
    betas(False, False)
    assert i1profiler_device_for(ti1) is None


def test_the_pxf_carries_the_name_and_the_default_is_unchanged(tmp_path):
    from workflow.i1profiler_export import Target, write_pxf
    t = Target("x", "RGB", ["R", "G", "B"], [(1, {"R": 1.0, "G": 2.0,
                                                  "B": 3.0})])
    write_pxf(t, tmp_path / "a.pxf", "x")
    assert 'MeasurementDevice="i1iSis"' in (tmp_path / "a.pxf").read_text(
        "utf-8")
    write_pxf(t, tmp_path / "b.pxf", "x", measurement_device="i1iO 2")
    assert 'MeasurementDevice="i1iO 2"' in (tmp_path / "b.pxf").read_text(
        "utf-8")
