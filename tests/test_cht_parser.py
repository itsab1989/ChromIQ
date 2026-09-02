"""Parse every standard Argyll .cht and check our box expansion against Argyll's
own declared ``BOXES n`` count — the strongest ground-truth self-check for the
scanner-target grid (Knut #98, ask 3). Also covers the multi-area (Wolf Faust)
case and the label-range expander."""
from __future__ import annotations

from pathlib import Path

import pytest

from workflow.cht_parser import (
    ChtParseError, expand_range, n_expanded, parse_cht)

# The 25 .cht files ship with Argyll; located next to the configured bin dir.
from tests.argyll_env import argyll_ref_dir
_ARGYLL_REF = argyll_ref_dir()
_CHT_FILES = sorted(_ARGYLL_REF.glob("*.cht")) if _ARGYLL_REF else []


def test_expand_range_numeric_alpha_gs_prefixed():
    assert expand_range("01", "05") == ["01", "02", "03", "04", "05"]
    assert expand_range("A", "D") == ["A", "B", "C", "D"]
    assert expand_range("GS00", "GS03") == ["GS00", "GS01", "GS02", "GS03"]
    assert expand_range("2A", "2C") == ["2A", "2B", "2C"]
    assert expand_range("_", "_") == ["_"]
    # Excel-style multi-letter wrap.
    assert expand_range("Y", "AB") == ["Y", "Z", "AA", "AB"]


@pytest.mark.skipif(not _CHT_FILES, reason="Argyll ref/ .cht files not present")
@pytest.mark.parametrize("cht", _CHT_FILES, ids=lambda p: p.name)
def test_box_count_matches_argyll_declared(cht: Path):
    """Every expanded box (colour patches + diagnostics) must equal the file's
    own ``BOXES n`` header — proves our F/X/Y/D expansion matches Argyll for
    all target types."""
    geom = parse_cht(cht.read_text(errors="ignore", encoding="utf-8"))
    assert n_expanded(geom) == geom.n_declared, (
        f"{cht.name}: expanded {n_expanded(geom)} != declared {geom.n_declared}")


@pytest.mark.skipif(not _CHT_FILES, reason="Argyll ref/ .cht files not present")
@pytest.mark.parametrize("cht", _CHT_FILES, ids=lambda p: p.name)
def test_every_cht_has_four_fiducials(cht: Path):
    geom = parse_cht(cht.read_text(errors="ignore", encoding="utf-8"))
    assert len(geom.fiducials) == 4


def test_wolf_faust_it8_two_patch_areas():
    """it8.cht = a 22×12 main grid (A01..L22) + a 24-cell greyscale strip
    (GS00..GS23) = 288 colour patches, two distinct areas."""
    if _ARGYLL_REF is None:
        pytest.skip("Argyll ref/ not present")
    cht = _ARGYLL_REF / "it8.cht"
    if not cht.is_file():
        pytest.skip("it8.cht not present")
    geom = parse_cht(cht.read_text(errors="ignore", encoding="utf-8"))
    names = {b.name for b in geom.patches}
    assert "A01" in names and "L22" in names          # main grid corners
    assert "GS00" in names and "GS23" in names          # greyscale strip
    assert len(geom.patches) == 288
    # Greyscale strip sits below the main grid (larger y = further down).
    grid_y = max(b.y2 for b in geom.patches if b.name == "L22")
    gs_y = min(b.y1 for b in geom.patches if b.name == "GS00")
    assert gs_y >= grid_y - geom.box_shrink


def test_parse_rejects_non_cht():
    with pytest.raises(ChtParseError):
        parse_cht("this is not a cht file\nBOXES 0\n")
