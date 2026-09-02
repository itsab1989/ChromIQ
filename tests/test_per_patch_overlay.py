"""#134: per_patch_overlay() turns a measured .ti3 + its chart .ti2 into the
{loc, exyz, xyz, de} patch list the split-patch overlay renders — reusing the
Measurement Report's D50-correct expected values."""
from __future__ import annotations

from pathlib import Path

from workflow.measurement_report import per_patch_overlay

_TI2 = """CTI1

NUMBER_OF_FIELDS 8
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 3
BEGIN_DATA
1 "A1" 100 100 100 96.42 100.00 82.53
2 "A2" 0 0 0 0.96 1.00 0.83
3 "A3" 100 0 0 41.00 21.00 2.00
END_DATA
"""

# Measured .ti3: same SAMPLE_IDs, XYZ nudged so ΔE is non-zero.
_TI3 = """CTI3

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 3
BEGIN_DATA
1 100 100 100 95.00 99.00 81.00
2 0 0 0 1.10 1.10 0.90
3 100 0 0 40.00 20.50 2.20
END_DATA
"""


def _write(tmp_path: Path):
    ti2 = tmp_path / "chart.ti2"; ti2.write_text(_TI2, encoding="utf-8")
    ti3 = tmp_path / "chart.ti3"; ti3.write_text(_TI3, encoding="utf-8")
    return ti2, ti3


def test_overlay_items_shape_and_match(tmp_path):
    ti2, ti3 = _write(tmp_path)
    items = per_patch_overlay(ti3, ti2)
    assert len(items) == 3
    locs = [it["loc"] for it in items]
    assert locs == ["A1", "A2", "A3"]
    for it in items:
        assert set(it) == {"loc", "exyz", "xyz", "de"}
        assert len(it["exyz"]) == 3 and len(it["xyz"]) == 3
        assert it["de"] >= 0
    # White patch: expected XYZ ~ the .ti2 design, measured ~ the .ti3 value.
    a1 = next(it for it in items if it["loc"] == "A1")
    assert abs(a1["exyz"][1] - 100.0) < 1.0          # expected Y
    assert abs(a1["xyz"][1] - 99.0) < 1.0            # measured Y
    assert a1["de"] > 0                              # nudged → some ΔE


def test_overlay_auto_finds_reference_ti2(tmp_path):
    ti2, ti3 = _write(tmp_path)
    # No ti2 passed → it locates the sibling chart.ti2 next to the .ti3.
    assert len(per_patch_overlay(ti3)) == 3


def test_foreign_ti3_no_matching_ids_returns_empty(tmp_path):
    ti2, _ = _write(tmp_path)
    foreign = tmp_path / "foreign.ti3"
    foreign.write_text(_TI3.replace("\n1 ", "\n901 ")
                            .replace("\n2 ", "\n902 ")
                            .replace("\n3 ", "\n903 "), encoding="utf-8")
    assert per_patch_overlay(foreign, ti2) == []


def test_missing_reference_returns_empty(tmp_path):
    _, ti3 = _write(tmp_path)
    (tmp_path / "chart.ti2").unlink()
    assert per_patch_overlay(ti3, tmp_path / "does-not-exist.ti2") == []
