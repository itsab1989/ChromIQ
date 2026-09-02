"""#150 (Knut): a ``.ti1`` holds three tables, and only the first is patches.

    *"the number of patches added in the swatch window includes the patches
    defined in table 2 and 3 in the .ti1 file. Only the first table of patches
    should be imported into the editor … The ti1 file added has 2002 patches,
    but import added 2019 patches."*

He is right, and 2002 + 8 + 9 = 2019 exactly. What the later tables hold:

===== ============================== ========= ==================================
Table Header key                     Key field What it is
===== ============================== ========= ==================================
1     ``NUMBER_OF_SETS``             SAMPLE_ID the patches to print
2     ``DENSITY_EXTREME_VALUES``     INDEX     the 8 RGB cube corners
3     ``DEVICE_COMBINATION_VALUES``  INDEX     those corners plus mid grey
===== ============================== ========= ==================================

Tables 2 and 3 are reference values printtarg expects; ChromIQ writes them
itself. They are not patches.

The same fault had a second, unreported victim. ``chart_exports`` had its own
copy of the reader, and its field list *accumulated* across tables — 21 names
with ``RGB_R`` three times, so the lookup resolved to column 15 on 7-wide rows,
every row was skipped, and ``-colours.txt`` came out **empty**. Confirmed in
Knut's own project: both of his exported sidecars are 0 bytes. That is why both
readers now share one implementation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from workflow.chart_exports import write_colours_txt
from workflow.i1profiler_import import parse_cgats, read_first_cgats_table

HEADER = """CTI1

DESCRIPTOR "Argyll Calibration Target chart information 1"
ORIGINATOR "ChromIQ"
COLOR_REP "iRGB"

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 3
BEGIN_DATA
1 0.0000 0.0000 0.0000 0.9505 1.0000 1.0890
2 100.0000 0.0000 0.0000 41.7781 22.0474 2.9997
3 100.0000 100.0000 100.0000 95.0500 100.0000 108.9000
END_DATA
"""

# targen's second and third tables, verbatim in shape: keyed INDEX, not
# SAMPLE_ID, and holding reference values rather than patches.
EXTRA_TABLES = """CTI1

DESCRIPTOR "Argyll Calibration Target chart information 1"
DENSITY_EXTREME_VALUES "2"

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
INDEX RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 2
BEGIN_DATA
0 100.0000 100.0000 100.0000 95.0500 100.0000 108.9000
1 0.0000 0.0000 0.0000 0.9505 1.0000 1.0890
END_DATA
CTI1

DESCRIPTOR "Argyll Calibration Target chart information 1"
DEVICE_COMBINATION_VALUES "2"

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
INDEX RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 2
BEGIN_DATA
0 50.0000 50.0000 50.0000 21.0917 22.1901 24.1650
1 0.0000 100.0000 0.0000 36.3529 71.8048 12.8898
END_DATA
"""


@pytest.fixture
def three_table_ti1(tmp_path) -> Path:
    p = tmp_path / "chart.ti1"
    p.write_text(HEADER + EXTRA_TABLES, encoding="utf-8")
    return p


@pytest.fixture
def one_table_ti1(tmp_path) -> Path:
    p = tmp_path / "plain.ti1"
    p.write_text(HEADER, encoding="utf-8")
    return p


# --- #150 itself ------------------------------------------------------------

def test_only_the_first_table_is_imported(three_table_ti1):
    """The reported bug: the reference tables were imported as patches."""
    patches = parse_cgats(three_table_ti1)
    assert len(patches) == 3, (
        "the density-extreme and device-combination tables were imported as "
        "patches — this is #150")


def test_the_imported_patches_are_the_right_ones(three_table_ti1):
    """Counting right by accident is not enough — the values must be table 1's,
    not a mixture."""
    got = [(round(p.r), round(p.g), round(p.b))
           for p in parse_cgats(three_table_ti1)]
    assert got == [(0, 0, 0), (100, 0, 0), (100, 100, 100)]


def test_a_single_table_file_is_unchanged(one_table_ti1):
    """Most files have one table; they must read exactly as before."""
    assert len(parse_cgats(one_table_ti1)) == 3


# --- the unreported victim: the hand-off sidecar ----------------------------

def test_colours_sidecar_is_not_empty(three_table_ti1, tmp_path):
    """``-colours.txt`` is what a user hands to a print shop. It was written
    empty for every ChromIQ-generated chart."""
    out = tmp_path / "chart-colours.txt"
    write_colours_txt(three_table_ti1, out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines, "the -colours.txt hand-off sidecar was written empty"
    assert len(lines) == 3
    assert lines == ["#000000", "#ff0000", "#ffffff"]


def test_colours_sidecar_ignores_the_reference_tables(three_table_ti1, tmp_path):
    """Mid grey (50/50/50) only exists in the third table, so its presence
    would prove the reference values leaked into the hand-off file."""
    out = tmp_path / "c.txt"
    write_colours_txt(three_table_ti1, out)
    assert "#808080" not in out.read_text(encoding="utf-8")


# --- the structural hazard behind both --------------------------------------

def test_field_names_come_from_the_first_table_alone(three_table_ti1):
    """The old readers kept every table's field names. That is what made the
    column lookup resolve past the end of the row."""
    fields, rows = read_first_cgats_table(three_table_ti1)
    assert fields == ["SAMPLE_ID", "RGB_R", "RGB_G", "RGB_B",
                      "XYZ_X", "XYZ_Y", "XYZ_Z"]
    assert fields.count("RGB_R") == 1
    assert all(len(r) == len(fields) for r in rows), (
        "every row must match the field list it is read with")


def test_a_later_table_with_a_different_layout_cannot_shift_the_columns(tmp_path):
    """The tables need not share a column order. A reader that took the last
    format but every table's rows would read RGB from the wrong columns and
    report plausible, wrong colours instead of failing."""
    odd = HEADER + """CTI1

DESCRIPTOR "reordered"
NUMBER_OF_FIELDS 4
BEGIN_DATA_FORMAT
RGB_B RGB_G RGB_R INDEX
END_DATA_FORMAT

NUMBER_OF_SETS 1
BEGIN_DATA
100.0000 0.0000 0.0000 0
END_DATA
"""
    p = tmp_path / "odd.ti1"
    p.write_text(odd, encoding="utf-8")
    got = [(round(x.r), round(x.g), round(x.b)) for x in parse_cgats(p)]
    assert got == [(0, 0, 0), (100, 0, 0), (100, 100, 100)]


def test_an_empty_file_still_raises(tmp_path):
    """A file with no table at all must say so, not return nothing quietly."""
    p = tmp_path / "empty.ti1"
    p.write_text("CTI1\n\nDESCRIPTOR \"nothing here\"\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_cgats(p)
