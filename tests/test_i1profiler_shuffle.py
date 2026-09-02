"""Nelson / pharmacist: an opt-in shuffled i1Profiler .pxf copy.

i1Profiler lays a chart out in patch-list order, so a systematically ordered
export can place near-identical patches side by side. ``also_shuffled`` writes
a second copy with the rows shuffled (ScramblePatches stays False so i1Profiler
keeps our order), leaving the primary export untouched."""
from __future__ import annotations

import re

import pytest

from workflow.i1profiler_export import (_shuffled_target, export_from_ti1,
                                        parse_ti1)


def _write_rgb_ti1(path, n=12):
    lines = ["CTI1", 'COLOR_REP "iRGB"', "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B", "END_DATA_FORMAT", "BEGIN_DATA"]
    for i in range(1, n + 1):
        v = round(i * 100 / n, 2)
        lines.append(f"{i} {v} {v} {v}")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _sids(txt_path):
    return [ln.split()[0] for ln in txt_path.read_text(encoding="utf-8").splitlines()
            if ln[:1].isdigit()]


def test_shuffle_is_a_permutation_and_reproducible_with_seed(tmp_path):
    ti1 = _write_rgb_ti1(tmp_path / "chart.ti1")
    tgt = parse_ti1(ti1)
    a = _shuffled_target(tgt, seed=99)
    b = _shuffled_target(tgt, seed=99)
    ids_a = [r[0] for r in a.rows]
    assert ids_a == [r[0] for r in b.rows]                 # seed reproducible
    assert sorted(ids_a) == sorted(r[0] for r in tgt.rows)  # same patch set
    assert ids_a != [r[0] for r in tgt.rows]                # order actually changed
    assert [r[1] for r in a.rows] != [] and len(a.rows) == len(tgt.rows)


def test_off_by_default_writes_only_the_primary_pair(tmp_path):
    ti1 = _write_rgb_ti1(tmp_path / "chart.ti1")
    export_from_ti1(ti1, tmp_path, base_name="out")
    assert (tmp_path / "out.pxf").is_file()
    assert (tmp_path / "out.txt").is_file()
    assert not (tmp_path / "out-shuffled.pxf").exists()
    assert not (tmp_path / "out-shuffled.txt").exists()


def test_also_shuffled_writes_second_copy_with_suffix(tmp_path):
    ti1 = _write_rgb_ti1(tmp_path / "chart.ti1")
    txt, pxf = export_from_ti1(ti1, tmp_path, base_name="out",
                               also_shuffled=True, shuffle_seed=7)
    # Return value is always the primary pair.
    assert pxf == tmp_path / "out.pxf"
    assert txt == tmp_path / "out.txt"
    for p in ("out.pxf", "out.txt", "out-shuffled.pxf", "out-shuffled.txt"):
        assert (tmp_path / p).is_file(), p
    # Primary keeps TI1 order; the shuffled copy is the same set, reordered.
    prim = _sids(tmp_path / "out.txt")
    shuf = _sids(tmp_path / "out-shuffled.txt")
    assert prim == [str(i) for i in range(1, 13)]
    assert sorted(shuf) == sorted(prim) and shuf != prim
    # i1Profiler must keep our order, not re-scramble on import.
    assert 'ScramblePatches="False"' in (tmp_path / "out-shuffled.pxf").read_text(encoding="utf-8")


def test_shuffle_works_for_cmyk_plus_n_pxf_only(tmp_path):
    # CMYK+N ships no .txt; the shuffled copy is a .pxf just like the primary.
    lines = ["CTI1", 'COLOR_REP "iCMYKOGV"', "BEGIN_DATA_FORMAT",
             "SAMPLE_ID CMYK_C CMYK_M CMYK_Y CMYK_K CMYK_O CMYK_G CMYK_V",
             "END_DATA_FORMAT", "BEGIN_DATA"]
    for i in range(1, 9):
        lines.append(f"{i} {i*5} {i*4} {i*3} {i*2} {i} {i} {i}")
    lines += ["END_DATA", ""]
    ti1 = tmp_path / "cmykn.ti1"
    ti1.write_text("\n".join(lines), encoding="utf-8")
    txt, pxf = export_from_ti1(ti1, tmp_path, base_name="out",
                               also_shuffled=True, shuffle_seed=3)
    assert txt is None                                    # no CGATS .txt for +N
    assert (tmp_path / "out.pxf").is_file()
    assert (tmp_path / "out-shuffled.pxf").is_file()
    assert not (tmp_path / "out-shuffled.txt").exists()
