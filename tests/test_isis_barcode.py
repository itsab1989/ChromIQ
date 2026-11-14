"""The i1iSis barcode: content and checksum as i1Profiler writes them.

Decoded from i1Profiler 3.8.8's own charts (REQUIREMENTS v2 §0, §3; the
challenge's M1): the checksum is the DECIMAL sum of the ASCII codes of
everything before it, the trailing ``*`` included, which X-Rite's two
guideline examples confirm (``1*`` = 91, ``01010000*`` = 428)."""
from __future__ import annotations

import pytest

from workflow.isis import chart as C


@pytest.mark.parametrize("grid,page,title,want", [
    (C.Grid(27, 18, 2, 28, 33, 957), 1, "V06_isis_A4_bc",
     "121B00001 V06*ISIS*A4*BC*1405"),
    (C.Grid(27, 18, 2, 28, 33, 957), 2, "V06_isis_A4_bc",
     "121B00002 V06*ISIS*A4*BC*1406"),
    (C.Grid(42, 23, 1, 42, 23, 957), 1, "V16_isisXL_A3_bc_tight",
     "172A00001 V16*ISISXL*A3*BC*TIGHT*2000"),
])
def test_i1profilers_three_barcodes(grid, page, title, want):
    assert C.barcode_text(grid, page, title) == want


@pytest.mark.parametrize("body,checksum", [("1*", 91), ("01010000*", 428)])
def test_the_guidelines_examples_are_decimal(body, checksum):
    assert sum(ord(c) for c in body) == checksum


def test_patch_sizes_in_quarter_millimetres():
    g = C.Grid(10, 10, 1, 10, 10, 100)
    assert C.barcode_text(g, 1, "X", 8.0, 7.25).startswith("0A0A0805")


def test_characters_code_39_lacks_become_stars():
    assert C.barcode_title("Moab_Satin-240 ä") == "MOAB*SATIN-240 *"


def test_the_bars_start_at_the_grid_and_read_bottom_to_top():
    bars = C.barcode_bars("12", 15.0, 41.5)
    assert min(b[0] for b in bars) == 15.0
    assert all(b[2] == 4.0 for b in bars)
    # "1" is the element's first character: at the bottom, its first
    # module a wide bar ending at the block's bottom edge
    first = max(bars, key=lambda b: b[1])
    assert abs(first[1] + first[3] - (41.5 + 13.0)) < 1e-9
    assert first[3] == 1.0


def test_a_title_too_long_for_the_chart_is_shortened():
    g = C.Grid(5, 10, 1, 5, 10, 50)
    t = C.fitting_title(g, 50.0, "A_VERY_LONG_CHART_NAME_INDEED")
    assert 0 < len(t) < len("A_VERY_LONG_CHART_NAME_INDEED")
    assert C.barcode_elements(C.barcode_text(g, 1, t)) * 5 - 1 <= 50.0
