"""Averaging repeated scanner .ti3 reads (Knut #98, ask 1c). Argyll `average`
can't do this (device RGB varies between scans); we average the RGB columns
ourselves, keeping the reference XYZ."""
from __future__ import annotations

import math

import pytest

from workflow.ti3_average import Ti3AverageError, average_scanner_ti3


def _write_ti3(path, rgb_by_id, xyz=(50.0, 50.0, 50.0)):
    lines = [
        'CTI3', 'DEVICE_CLASS "INPUT"', 'COLOR_REP "RGB_XYZ"',
        'NUMBER_OF_FIELDS 7', 'BEGIN_DATA_FORMAT',
        'SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z', 'END_DATA_FORMAT',
        f'NUMBER_OF_SETS {len(rgb_by_id)}', 'BEGIN_DATA',
    ]
    for sid, (r, g, b) in rgb_by_id.items():
        lines.append(f'{sid} {r} {g} {b} {xyz[0]} {xyz[1]} {xyz[2]}')
    lines += ['END_DATA', '']
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_mean_averages_rgb_keeps_xyz(tmp_path):
    a = _write_ti3(tmp_path / "a.ti3", {"1": (10.0, 20.0, 30.0)})
    b = _write_ti3(tmp_path / "b.ti3", {"1": (20.0, 40.0, 50.0)})
    out = average_scanner_ti3([a, b], tmp_path / "avg.ti3", method="mean")
    row = [l for l in out.read_text(encoding="utf-8").splitlines()
           if l.startswith("1 ")][0].split()
    assert float(row[1]) == pytest.approx(15.0)   # (10+20)/2
    assert float(row[2]) == pytest.approx(30.0)   # (20+40)/2
    assert float(row[3]) == pytest.approx(40.0)   # (30+50)/2
    assert float(row[4]) == pytest.approx(50.0)   # XYZ untouched


def test_geomean(tmp_path):
    a = _write_ti3(tmp_path / "a.ti3", {"1": (10.0, 10.0, 10.0)})
    b = _write_ti3(tmp_path / "b.ti3", {"1": (40.0, 40.0, 40.0)})
    out = average_scanner_ti3([a, b], tmp_path / "g.ti3", method="geomean")
    row = [l for l in out.read_text(encoding="utf-8").splitlines()
           if l.startswith("1 ")][0].split()
    assert float(row[1]) == pytest.approx(math.sqrt(10.0 * 40.0))  # =20, not 25


def test_trimmed_drops_extremes_with_three_plus(tmp_path):
    files = []
    for i, r in enumerate((10.0, 12.0, 100.0)):     # 100 is an outlier scan
        files.append(_write_ti3(tmp_path / f"{i}.ti3", {"1": (r, r, r)}))
    out = average_scanner_ti3(files, tmp_path / "t.ti3", method="trimmed")
    row = [l for l in out.read_text(encoding="utf-8").splitlines()
           if l.startswith("1 ")][0].split()
    assert float(row[1]) == pytest.approx(12.0)     # drop 10 & 100 → just 12


def test_mismatched_patch_sets_raise(tmp_path):
    a = _write_ti3(tmp_path / "a.ti3", {"1": (10.0, 10.0, 10.0)})
    b = _write_ti3(tmp_path / "b.ti3", {"2": (10.0, 10.0, 10.0)})
    with pytest.raises(Ti3AverageError):
        average_scanner_ti3([a, b], tmp_path / "x.ti3")


def test_single_input_raises(tmp_path):
    a = _write_ti3(tmp_path / "a.ti3", {"1": (10.0, 10.0, 10.0)})
    with pytest.raises(Ti3AverageError):
        average_scanner_ti3([a], tmp_path / "x.ti3")
