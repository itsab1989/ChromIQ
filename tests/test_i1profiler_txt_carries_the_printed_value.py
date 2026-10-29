"""The i1Profiler .txt patch set carries the whole number ChromIQ prints.

jctay (forum, 2026-10-29): i1Profiler cuts the fraction off an RGB value in a
CGATS .txt patch set instead of rounding it. Measured in i1Profiler 3.8.8 the
same day: a .txt holding 42.5000 / 127.5000 / 84.9999 is kept as 42 / 127 / 84
(load it, save the patch set as .pxf), while i1Profiler draws its own test
chart from the rounded value (43 / 128 / 85). ChromIQ wrote ``v * 2.55`` with
four decimals, so a 7-step grid chart (16.66667 %) was one level low there.

The .pxf had its own slip: ``round(v * 2.55)`` turns 50 % into 127 and 90 %
into 229, because 2.55 is not exact in binary, while the chart printtarg and
the layout engine print carries 128 and 230.

So every i1Profiler file now carries the printed value, in whole numbers.
"""
from __future__ import annotations

import re
from pathlib import Path

from workflow.i1profiler_export import export_from_ti1, parse_ti1, write_pwxf
from workflow.i1profiler_import import parse_cgats, parse_pxf
from workflow.layout_engine.colorants import to_display_rgb

# Values targen writes for 7- and 11-step grids, and the edges.
LEVELS = ["0.00000", "10.0000", "16.66667", "30.0000", "33.33333", "50.0000",
          "66.66667", "70.0000", "83.33333", "90.0000", "100.0000"]
# What ChromIQ prints for them (printtarg and the layout engine agree, measured
# on real TIFFs 2026-10-29).
PRINTED = [0, 26, 43, 76, 85, 128, 170, 178, 212, 230, 255]


def _ti1(tmp_path: Path) -> Path:
    rows = [f"{i} {v} {v} {v} 50.0 50.0 50.0" for i, v in enumerate(LEVELS, 1)]
    text = "\n".join([
        "CTI1", "", 'COLOR_REP "iRGB"', "",
        "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT", "",
        f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA", *rows, "END_DATA", ""])
    p = tmp_path / "grid.ti1"
    p.write_text(text, encoding="utf-8")
    return p


def _txt_values(txt: Path) -> list[str]:
    lines = txt.read_text(encoding="utf-8").splitlines()
    data = lines[lines.index("BEGIN_DATA") + 1:lines.index("END_DATA")]
    return [line.split()[1] for line in data]


def _pxf_values(text: str) -> list[int]:
    return [int(v) for v in re.findall(r"<cc:R>(\d+)</cc:R>", text)]


def test_the_txt_holds_whole_numbers_with_nothing_for_i1profiler_to_cut(tmp_path):
    txt, _ = export_from_ti1(_ti1(tmp_path), tmp_path)
    values = _txt_values(txt)
    assert all(float(v).is_integer() for v in values), values
    assert [int(float(v)) for v in values] == PRINTED


def test_the_txt_the_pxf_and_the_printed_chart_agree(tmp_path):
    ti1 = _ti1(tmp_path)
    txt, pxf = export_from_ti1(ti1, tmp_path)
    printed = [to_display_rgb((float(v),) * 3, "iRGB")[0] for v in LEVELS]
    assert printed == PRINTED
    assert [int(float(v)) for v in _txt_values(txt)] == PRINTED
    assert _pxf_values(pxf.read_text(encoding="utf-8")) == PRINTED


def test_the_workflow_file_carries_the_printed_value_too(tmp_path):
    out = tmp_path / "grid.pwxf"
    write_pwxf(parse_ti1(_ti1(tmp_path)), out, "grid")
    assert _pxf_values(out.read_text(encoding="utf-8")) == PRINTED


def test_cmyk_percentages_keep_their_decimals(tmp_path):
    """i1Profiler 3.8.8 keeps a CMYK .txt to four decimals (16.6667 stays
    16.6667 in the patch set it saves), so those are left as they are."""
    p = tmp_path / "cmyk.ti1"
    p.write_text("\n".join([
        "CTI1", "", 'COLOR_REP "CMYK"', "", "NUMBER_OF_FIELDS 5",
        "BEGIN_DATA_FORMAT", "SAMPLE_ID CMYK_C CMYK_M CMYK_Y CMYK_K",
        "END_DATA_FORMAT", "", "NUMBER_OF_SETS 1", "BEGIN_DATA",
        "1 16.66667 33.33333 50.00000 0.00000", "END_DATA", ""]), encoding="utf-8")
    txt, _ = export_from_ti1(p, tmp_path)
    row = txt.read_text(encoding="utf-8").split("BEGIN_DATA\n")[1].splitlines()[0]
    assert row.split() == ["1", "16.6667", "33.3333", "50.0000", "0.0000"]


def test_an_old_fractional_txt_still_reads_back_onto_the_same_patches(tmp_path):
    """A .txt written by 4.3.19 or older (42.5000, 127.5000 ...) still imports,
    and lands within a fraction of a level of the new whole-number file."""
    ti1 = _ti1(tmp_path)
    txt, _ = export_from_ti1(ti1, tmp_path)
    old = tmp_path / "old.txt"
    text = txt.read_text(encoding="utf-8")
    head, rest = text.split("BEGIN_DATA\n", 1)
    rows = [f"{i} {float(v) * 2.55:.4f} {float(v) * 2.55:.4f} {float(v) * 2.55:.4f} "
            for i, v in enumerate(LEVELS, 1)]
    old.write_text(head + "BEGIN_DATA\n" + "\n".join(rows) + "\nEND_DATA\n",
                   encoding="utf-8")
    new_p, old_p = parse_cgats(txt), parse_cgats(old)
    assert len(new_p) == len(old_p) == len(LEVELS)
    for a, b, want in zip(new_p, old_p, LEVELS):
        assert abs(a.r - float(want)) < 0.2      # half a level is 0.196
        assert abs(a.r - b.r) < 0.2
    _, pxf = export_from_ti1(ti1, tmp_path)
    assert [round(p.r * 2.55) for p in parse_pxf(pxf)] == PRINTED
