"""The i1Profiler patch set (.pxf) in every combination of the FD-9, i1iO and
i1iSis Beta switches (review of a7ca1489e, M3, kept as a deliberate fix of
the i1iO Beta).

* The i1iO Beta off: every chart's .pxf is the file 4.3.37 wrote
  (MeasurementDevice "i1iSis", the long-standing default), byte for byte.
* The i1iO Beta on: only an i1iO chart's .pxf differs, and only in its
  MeasurementDevice ("i1iO 2", i1Profiler's own name), whatever the i1iSis
  switch says.
* The i1iSis Beta on: only an i1iSis chart's .pxf names the i1iSis.
* The FD-9 and every other instrument: byte for byte the same in all eight
  combinations.

The "4.3.37 file" is the writer's own default path (no device asked for);
`scripts/compare_with_release.py` compares the exports with the v4.3.37 tag
itself.
"""
from __future__ import annotations

import itertools
import shutil
from pathlib import Path

import pytest

CODES = ("i1", "p3", "CM", "SS", "CR30", "FD9", "IO2", "XRISIS")
SWITCHES = ("fd9", "i1io", "isis")


def _set(on: dict) -> list:
    import importlib
    before = []
    for name in SWITCHES:
        m = importlib.import_module(f"workflow.{name}.support")
        before.append((m, m._latched))
        m.set_enabled_for_this_process(bool(on.get(name)))
    return before


def _restore(before) -> None:
    for m, b in before:
        m._latched = b


def _ti1(path: Path, n: int) -> Path:
    rows = "\n".join(f"{i + 1} {i % 100:.4f} {(i * 7) % 100:.4f} "
                     f"{(i * 13) % 100:.4f} 50.0 50.0 50.0"
                     for i in range(n))
    path.write_text(
        "CTI1\n\nDESCRIPTOR \"Argyll Calibration Target chart information "
        "1\"\nCOLOR_REP \"RGB\"\n\nNUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n{rows}\nEND_DATA\n",
        encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def charts(tmp_path_factory):
    """One chart per instrument, built with every Beta on."""
    from workflow.layout_engine import chart
    root = tmp_path_factory.mktemp("pxf_charts")
    before = _set({k: True for k in SWITCHES})
    out = {}
    try:
        for code in CODES:
            d = root / code
            d.mkdir()
            src = _ti1(d / "src.ti1", 120)
            chart.build_chart(src, d / "chart", instrument=code, paper="A4",
                              dpi=72, seed=1234, project="Proof chart",
                              chart_date="2026-01-01")
            shutil.copyfile(src, d / "chart.ti1")
            out[code] = d / "chart.ti1"
    finally:
        _restore(before)
    return out


def _reference(ti1: Path, out: Path) -> bytes:
    """The .pxf written without a device asked for: 4.3.37's file."""
    from workflow.i1profiler_export import export_from_ti1
    _txt, pxf = export_from_ti1(ti1, out, base_name="ref-i1profiler",
                                descriptor="chart")
    return Path(pxf).read_bytes()


@pytest.mark.parametrize("combo", list(itertools.product((False, True),
                                                         repeat=3)))
def test_the_pxf_in_every_switch_combination(charts, tmp_path, combo):
    from workflow.chart_exports import write_sidecars
    on = dict(zip(SWITCHES, combo))
    before = _set(on)
    try:
        for code, ti1 in charts.items():
            out = tmp_path / code
            ref = _reference(ti1, out)
            write_sidecars(ti1, out, "chart")
            got = (out / "chart-i1profiler.pxf").read_bytes()
            if code == "IO2" and on["i1io"]:
                assert got != ref
                assert got.replace(b'MeasurementDevice="i1iO 2"',
                                   b'MeasurementDevice="i1iSis"') == ref
            elif code == "XRISIS" and on["isis"]:
                assert b'MeasurementDevice="i1iSis' in got
                assert got.replace(b'MeasurementDevice="i1iSis XL"',
                                   b'MeasurementDevice="i1iSis"') == ref
            else:
                assert got == ref, (code, on)
    finally:
        _restore(before)
