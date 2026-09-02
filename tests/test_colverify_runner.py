"""Tools → "Verify against reference" (colverify wrapper).

Covers, without needing the Argyll binary:
  * parsing pasted reference tables (Lab/XYZ, index- and name-prefixed rows);
  * the reference .ti3 emitter (SAMPLE_ID 1..N, correct PCS fields, optional RGB);
  * chart patch-count cross-check reading only the first CGATS table;
  * colverify argument construction and summary/per-patch parsing.

If the colverify binary is present, an end-to-end run asserts a zero-error
self-comparison.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from core.resource_path import argyll_binary
from tests.argyll_env import argyll_tool
from workflow.colverify_runner import (
    ColverifyParams,
    ColverifyRunner,
    PatchDelta,
    chart_patch_count,
    interpret,
    parse_reference_values,
    vrml_output_path,
    write_reference_ti3,
)


# --- reference table parsing ----------------------------------------------

def test_parse_plain_triples():
    rows = parse_reference_values("100 0 0\n50.5 -1.2 3.4\n")
    assert rows == [(100.0, 0.0, 0.0), (50.5, -1.2, 3.4)]


def test_parse_tolerates_index_and_name_and_separators():
    text = "# header\n1, 100, 0, 0\nGS01\t50\t0\t0\n\n  2  95.0  -1.0  2.0 \n"
    assert parse_reference_values(text) == [
        (100.0, 0.0, 0.0),
        (50.0, 0.0, 0.0),
        (95.0, -1.0, 2.0),
    ]


def test_parse_rejects_short_line():
    with pytest.raises(ValueError, match="Line 2"):
        parse_reference_values("100 0 0\n50 0\n")


def test_parse_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        parse_reference_values("\n# only a comment\n")


# --- reference .ti3 emitter ------------------------------------------------

def test_write_reference_lab(tmp_path: Path):
    out = write_reference_ti3(
        tmp_path / "ref.ti3", [(100.0, 0.0, 0.0), (50.0, 1.0, -2.0)], space="LAB"
    )
    text = out.read_text(encoding="utf-8")
    assert "SAMPLE_ID LAB_L LAB_A LAB_B" in text
    assert "NUMBER_OF_SETS 2" in text
    assert 'DEVICE_CLASS "OUTPUT"' in text
    body = text.split("BEGIN_DATA\n", 1)[1].split("END_DATA", 1)[0].splitlines()
    assert body[0].split()[0] == "1"          # SAMPLE_ID starts at 1
    assert body[1].split()[0] == "2"
    assert body[0].split()[1:] == ["100.0000", "0.0000", "0.0000"]


def test_write_reference_xyz_with_rgb(tmp_path: Path):
    out = write_reference_ti3(
        tmp_path / "ref.ti3",
        [(95.0, 100.0, 108.0)],
        space="XYZ",
        rgb=[(100.0, 100.0, 100.0)],
    )
    text = out.read_text(encoding="utf-8")
    assert "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z" in text
    assert 'COLOR_REP "RGB_XYZ"' in text


def test_write_reference_rgb_length_mismatch(tmp_path: Path):
    with pytest.raises(ValueError, match="doesn't match"):
        write_reference_ti3(
            tmp_path / "ref.ti3", [(1.0, 2.0, 3.0)], rgb=[(0, 0, 0), (1, 1, 1)]
        )


# --- chart patch-count cross-check ----------------------------------------

def test_chart_patch_count_first_table_only(tmp_path: Path):
    # A .ti1-like file with three tables; only the first (3 rows) is the patch list.
    chart = tmp_path / "chart.ti1"
    chart.write_text(
        "BEGIN_DATA\n1 a\n2 b\n3 c\nEND_DATA\n"
        "BEGIN_DATA\nx\ny\nEND_DATA\n"
        "BEGIN_DATA\np\nq\nr\ns\nEND_DATA\n", encoding="utf-8"
    )
    assert chart_patch_count(chart) == 3


# --- colverify args + parsing ---------------------------------------------

def test_build_args_defaults(tmp_path: Path):
    p = ColverifyParams(ref_ti3=tmp_path / "ref.ti3", measured_ti3=tmp_path / "m.ti3")
    args = ColverifyRunner(None)._build_args(p)
    assert args == ["-v", "2", "-k", "-s", "ref.ti3", "m.ti3"]


def test_build_args_cie76_no_sort(tmp_path: Path):
    p = ColverifyParams(
        ref_ti3=tmp_path / "ref.ti3",
        measured_ti3=tmp_path / "m.ti3",
        de_formula="",
        sort=False,
        per_patch=False,
    )
    assert ColverifyRunner(None)._build_args(p) == ["ref.ti3", "m.ti3"]


def test_parse_results_summary_and_patches():
    log = (
        "Verify results:\n"
        "1: 100.0 0.0 0.0 <=> 99.5 0.1 -0.2  de 0.530000\n"
        "12: 50.0 1.0 -2.0 <=> 51.0 1.2 -2.1  de 1.040000\n"
        "  Total errors (CIEDE2000):     peak = 1.040000, avg = 0.785000\n"
        "  Worst 10% errors (CIEDE2000): peak = 1.040000, avg = 1.040000\n"
    )
    res = ColverifyRunner(None).parse_results(log)
    assert res.peak_de == pytest.approx(1.04)
    assert res.avg_de == pytest.approx(0.785)
    assert res.patch_errors == [("1", 0.53), ("12", 1.04)]


# --- gamut-skip arg + richer parsing --------------------------------------

def test_build_args_with_vrml(tmp_path: Path):
    p = ColverifyParams(
        ref_ti3=tmp_path / "ref.ti3", measured_ti3=tmp_path / "m.ti3", vrml=True,
    )
    args = ColverifyRunner(None)._build_args(p)
    assert args == ["-v", "2", "-k", "-s", "-w", "ref.ti3", "m.ti3"]


def test_vrml_output_path_swaps_extension(tmp_path: Path):
    assert vrml_output_path(tmp_path / "chart.ti3") == tmp_path / "chart.x3d.html"
    # multi-dot stems keep all but the final extension (colverify strips one)
    assert vrml_output_path(tmp_path / "a.b.ti3") == tmp_path / "a.b.x3d.html"


def test_build_args_with_gamut_profile(tmp_path: Path):
    prof = tmp_path / "matte.icc"
    p = ColverifyParams(
        ref_ti3=tmp_path / "ref.ti3",
        measured_ti3=tmp_path / "m.ti3",
        gamut_profile=prof,
    )
    args = ColverifyRunner(None)._build_args(p)
    assert args == ["-v", "2", "-k", "-s", "-L", str(prof), "ref.ti3", "m.ti3"]


_FULL_LOG = (
    "Verify results:\n"
    "1: 100.000000 0.000000 0.000000 <=> 99.500000 0.100000 -0.200000  de 0.530000\n"
    "12: 50.000000 1.000000 -2.000000 <=> 47.000000 1.200000 -2.100000  de 3.040000\n"
    "  Total errors (CIEDE2000):     peak = 3.040000, avg = 1.785000\n"
    "  Worst 10% errors (CIEDE2000): peak = 3.040000, avg = 3.040000\n"
    "  Best  90% errors (CIEDE2000): peak = 0.530000, avg = 0.530000\n"
    "  avg err X  1.0, Y  1.0, Z  1.0\n"
    "  avg err L* -1.750000, a* 0.150000, b* -0.150000\n"
)


def test_parse_full_patch_triples_and_extras():
    res = ColverifyRunner(None).parse_results(_FULL_LOG)
    assert res.avg_de == pytest.approx(1.785)
    assert res.worst10_avg == pytest.approx(3.04)
    assert res.best90_avg == pytest.approx(0.53)
    assert (res.comp_l, res.comp_a, res.comp_b) == pytest.approx((-1.75, 0.15, -0.15))
    # full per-patch triples captured
    assert len(res.patches) == 2
    assert res.patches[0].target == pytest.approx((100.0, 0.0, 0.0))
    assert res.patches[1].measured == pytest.approx((47.0, 1.2, -2.1))
    # backward-compatible flat list still populated, once per patch
    assert res.patch_errors == [("1", 0.53), ("12", 3.04)]


def test_parse_gamut_count():
    res = ColverifyRunner(None).parse_results(
        _FULL_LOG + "No of test patches in gamut = 42/50\n"
    )
    assert (res.in_gamut, res.total_patches) == (42, 50)


# --- PatchDelta lightness/colour split ------------------------------------

def test_patch_delta_lightness_dominated():
    # deep shadow on matte: big ΔL*, tiny Δa*b*  →  reachability, not colour error
    pd = PatchDelta("GS01", target=(5.0, 0.0, 0.0), measured=(22.0, 0.4, -0.3), de=17.0)
    assert pd.dl == pytest.approx(17.0)
    assert pd.dab == pytest.approx(0.5)
    assert pd.lightness_dominated is True


def test_patch_delta_colour_dominated():
    pd = PatchDelta("D5", target=(50.0, 0.0, 0.0), measured=(50.5, 6.0, -8.0), de=10.0)
    assert pd.lightness_dominated is False


# --- interpret() -----------------------------------------------------------

def test_interpret_no_result():
    assert "didn't return a result" in interpret(ColverifyRunner(None).parse_results(""))


def test_interpret_flags_lightness_lean():
    res = ColverifyRunner(None).parse_results(_FULL_LOG)
    text = interpret(res)
    assert "Average ΔE 1.78" in text
    assert "lightness" in text.lower()
    assert "darker" in text  # comp_l is negative → print came out darker


def test_interpret_flags_colour_lean():
    log = _FULL_LOG.replace(
        "avg err L* -1.750000, a* 0.150000, b* -0.150000",
        "avg err L* 0.100000, a* 3.000000, b* -2.000000",
    )
    text = interpret(ColverifyRunner(None).parse_results(log))
    assert "mostly in colour" in text


def test_interpret_explains_gamut_skip():
    res = ColverifyRunner(None).parse_results(
        _FULL_LOG + "No of test patches in gamut = 42/50\n"
    )
    text = interpret(res)
    assert "8 of 50" in text
    assert "left out" in text


# --- end-to-end (binary required) -----------------------------------------

def _argyll_bin(name: str) -> str | None:
    return argyll_tool(name) or shutil.which(argyll_binary(name))


def test_colverify_zero_error_self_compare(tmp_path: Path):
    binp = _argyll_bin("colverify")
    if not binp:
        pytest.skip("colverify binary not available")
    rows = [(100.0, 0.0, 0.0), (50.0, 1.0, -2.0), (20.0, -5.0, 8.0)]
    ref = write_reference_ti3(tmp_path / "ref.ti3", rows, space="LAB")
    out = subprocess.run(
        [binp, "-k", str(ref), str(ref)],
        capture_output=True, text=True, cwd=tmp_path, encoding="utf-8",
    )
    res = ColverifyRunner(None).parse_results(out.stdout)
    assert res.avg_de == pytest.approx(0.0, abs=1e-4)
    assert res.peak_de == pytest.approx(0.0, abs=1e-4)
