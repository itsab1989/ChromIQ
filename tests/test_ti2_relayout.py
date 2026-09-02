"""Tests for the TI2 layout-editor core (workflow/ti2_relayout.py).

Pure-logic tests run anywhere; the end-to-end test that shells out to printtarg
is skipped when ArgyllCMS isn't installed.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from tests.argyll_env import argyll_bin_dir, argyll_tool
from workflow import ti2_relayout as R

ARGYLL_BIN = argyll_bin_dir()
_HAS_ARGYLL = argyll_tool("printtarg") is not None
argyll = pytest.mark.skipif(not _HAS_ARGYLL, reason="ArgyllCMS not installed")


# --- a minimal but valid .ti2 fixture --------------------------------------
_TI2 = """CTI2

ORIGINATOR "test"
TARGET_INSTRUMENT "GretagMacbeth i1 Pro"
COLOR_REP "iRGB"
PAPER_SIZE "210.0x297.0"
APPROX_WHITE_POINT "95.1 100.0 108.8"

NUMBER_OF_FIELDS 8
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 4
BEGIN_DATA
1 "A1" 100.0 100.0 100.0 95.1 100.0 108.8
2 "A2" 0.0 0.0 0.0 0.0 0.0 0.0
3 "A3" 100.0 0.0 0.0 41.2 21.3 1.9
4 "B1" 0.0 0.0 100.0 18.0 7.2 95.0
END_DATA
"""


@pytest.fixture
def ti2(tmp_path: Path) -> Path:
    p = tmp_path / "src.ti2"
    p.write_text(_TI2, encoding="utf-8")
    return p


# --- parsing ---------------------------------------------------------------
def test_parse_basics(ti2: Path):
    spec = R.ChartSpec.from_ti2(ti2)
    assert len(spec.patches) == 4
    assert spec.dev_fields == ["RGB_R", "RGB_G", "RGB_B"]
    assert spec.has_xyz
    assert spec.instrument_flag == "i1"
    assert spec.paper_flag == "A4"
    assert spec.patches[0].loc == "A1"
    assert spec.patches[2].dev == (100.0, 0.0, 0.0)


# --- load_rgb_program (combine sets) ---------------------------------------
def test_load_rgb_program_from_ti2(ti2: Path):
    prog = R.load_rgb_program(ti2)
    # Same patches as the chart, in visual (SAMPLE_LOC) order, 3-tuple RGB.
    assert prog == [
        (100.0, 100.0, 100.0),
        (0.0, 0.0, 0.0),
        (100.0, 0.0, 0.0),
        (0.0, 0.0, 100.0),
    ]


def test_load_rgb_program_from_cgats_txt(tmp_path: Path):
    p = tmp_path / "set.txt"
    p.write_text(
        "BEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n"
        "BEGIN_DATA\n1 100 50 0\n2 0 0 100\nEND_DATA\n", encoding="utf-8"
    )
    prog = R.load_rgb_program(p)
    assert prog == [(100.0, 50.0, 0.0), (0.0, 0.0, 100.0)]


def test_load_rgb_program_from_pxf(tmp_path: Path):
    p = tmp_path / "set.pxf"
    p.write_text(
        '<?xml version="1.0"?>\n<Root><Object><ColorValues>'
        '<ColorRGB><R>100</R><G>0</G><B>50</B></ColorRGB>'
        '</ColorValues></Object></Root>', encoding="utf-8"
    )
    assert R.load_rgb_program(p) == [(100.0, 0.0, 50.0)]


def test_load_rgb_program_rejects_non_rgb_ti2(tmp_path: Path):
    p = tmp_path / "cmyk.ti2"
    p.write_text(_TI2.replace('"iRGB"', '"iCMYK"'), encoding="utf-8")
    with pytest.raises(ValueError, match="RGB"):
        R.load_rgb_program(p)


def test_new_chart_from_scratch(tmp_path: Path):
    spec = R.ChartSpec.new("i1", "A4")
    assert spec.patches == []
    assert spec.dev_fields == ["RGB_R", "RGB_G", "RGB_B"]
    assert spec.paper_mm == (210.0, 297.0)
    prog = [(100, 100, 100), (0, 0, 0), (50, 50, 50)]  # built up by the editor
    out = R.write_ti1(spec, prog, tmp_path / "c.ti1")
    assert out.read_text(encoding="utf-8").count("CTI1") == 3


def test_seed_parse_ignores_palette_tables(ti2: Path, tmp_path: Path):
    # write_ti1 emits 3 tables; the seed_from_targen parse (layout_engine's
    # ti1_reader since #72) must return only the patch list, not the palette
    # tables.
    from workflow.layout_engine.ti1_reader import read_ti1
    spec = R.ChartSpec.from_ti2(ti2)
    prog = R.default_program(spec)
    out = R.write_ti1(spec, prog, tmp_path / "c.ti1")
    got = [dev for dev, _xyz in read_ti1(out).patches]
    assert len(got) == len(prog)  # not len(prog) + 8 extremes + 9 combos
    assert got[2] == (100.0, 0.0, 0.0)


@argyll
def test_seed_from_targen_then_regenerate(tmp_path: Path):
    prog = R.seed_from_targen(ARGYLL_BIN, 30)
    assert 20 <= len(prog) <= 60          # ~requested count
    assert all(len(p) == 3 for p in prog)
    spec = R.ChartSpec.new("i1", "A4")    # new-from-scratch, seeded
    res = R.regenerate(spec, prog, tmp_path, ARGYLL_BIN)
    R.assert_data_integrity(prog, res.ti2)


_PROG4 = [(0.0, 0.0, 0.0), (100.0, 100.0, 100.0),
          (100.0, 0.0, 0.0), (0.0, 0.0, 100.0)]


@argyll
def test_regenerate_with_twin_false_skips_the_second_run(tmp_path: Path):
    """Fast preview (#44): with_twin=False renders only the deliverable."""
    spec = R.ChartSpec.new("i1", "A4")
    res = R.regenerate(spec, _PROG4, tmp_path / "notwin", ARGYLL_BIN,
                       with_twin=False)
    assert res.tiffs
    assert all(b is None for b in res.bw_tiffs)     # no twin produced
    # The default still renders a twin (Spacers mode / save path rely on it).
    res2 = R.regenerate(spec, _PROG4, tmp_path / "twin", ARGYLL_BIN)
    assert any(res2.bw_tiffs)


def test_per_strip_grids_zigzag_uses_own_offsets():
    """#48: double-density zig-zag — alternate strips offset by half a patch.
    Each clean strip keeps its own offset; unresolved strips use same parity."""
    steps = 4
    even = [10.0, 30.0, 50.0, 70.0]
    odd = [20.0, 40.0, 60.0, 80.0]          # shifted +10 (half pitch)
    clean = [even, odd, even, None]          # strip 3 unresolved (odd parity)
    lookup = R._per_strip_step_grids(clean, steps)
    assert lookup(0) == even
    assert lookup(1) == odd
    assert lookup(2) == even
    assert lookup(3) == odd                  # parity-matched fallback (odd)


def test_per_strip_grids_normal_chart_is_one_grid():
    """A non-zig-zag chart: all strips share a grid; an unresolved strip with no
    same-parity clean sibling falls back to the global median."""
    steps = 3
    g = [10.0, 20.0, 30.0]
    lookup = R._per_strip_step_grids([g, None, g], steps)   # only even clean
    assert lookup(0) == g
    assert lookup(1) == g                    # odd has none → global median (g)
    assert lookup(2) == g


def test_per_strip_grids_none_when_nothing_clean():
    assert R._per_strip_step_grids([None, None, None], 4) is None


@argyll
def test_regenerate_dpi_override_shrinks_the_preview(tmp_path: Path):
    """A dpi_override renders a smaller TIFF without changing the .ti2 (#44)."""
    from PIL import Image
    spec = R.ChartSpec.new("i1", "A4")
    full = R.regenerate(spec, _PROG4, tmp_path / "full", ARGYLL_BIN,
                        options=R.LayoutOptions(dpi=300), with_twin=False)
    low = R.regenerate(spec, _PROG4, tmp_path / "low", ARGYLL_BIN,
                       options=R.LayoutOptions(dpi=300), with_twin=False,
                       dpi_override=100)
    assert Image.open(low.tiffs[0]).size[0] < Image.open(full.tiffs[0]).size[0]


@argyll
def test_integrity_tolerates_8bit_boundary_rounding(tmp_path: Path):
    """Arbitrary-float patches (e.g. the colour-set generators) can land exactly
    on an 8-bit half-boundary, where our predicted code and printtarg's differ by
    one. That one-code shift must NOT be reported as a missing patch (issue:
    "requested patch … missing from regenerated chart")."""
    def boundary(c: int) -> float:
        return (c + 0.5) / 255 * 100
    prog = []
    for c in range(20, 240, 7):
        b = boundary(c)
        for eps in (-0.05, -0.01, 0.0, 0.01, 0.05):
            prog.append((b + eps, 50.0, 50.0))
    spec = R.ChartSpec.new("i1", "A4")
    res = R.regenerate(spec, prog, tmp_path, ARGYLL_BIN)
    R.assert_data_integrity(prog, res.ti2)        # no false "missing" alarm
    # A genuinely absent colour is still caught (off by the full distance).
    with pytest.raises(AssertionError):
        R.assert_data_integrity(prog + [(12.34, 78.9, 4.0)], res.ti2)


# --- "tag as randomised" gate + keyword rewrite ----------------------------

_TI2_HEAD = (
    'CTI2\n\nORIGINATOR "test"\nTARGET_INSTRUMENT "GretagMacbeth i1 Pro"\n'
    'COLOR_REP "iRGB"\n{kw} "2"\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
    "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
)


def _make_ti2(tmp_path: Path, strips: dict, kw: str = "CHART_ID") -> Path:
    """Write a minimal .ti2 from {strip_letter: [(r,g,b), ...]} (XYZ faked)."""
    rows, sid = [], 0
    for letter, seq in strips.items():
        for i, (r, g, b) in enumerate(seq, start=1):
            sid += 1
            rows.append(f'{sid} "{letter}{i}" {r:.1f} {g:.1f} {b:.1f} 0 0 0')
    text = _TI2_HEAD.format(kw=kw) + f"NUMBER_OF_SETS {sid}\nBEGIN_DATA\n" \
        + "\n".join(rows) + "\nEND_DATA\n"
    p = tmp_path / "chart.ti2"
    p.write_text(text, encoding="utf-8")
    return p


def test_analyze_safe_when_well_mixed(tmp_path: Path):
    strips = {
        "A": [(100, 0, 0), (0, 100, 0), (0, 0, 100)],
        "B": [(100, 100, 0), (0, 100, 100), (100, 0, 100)],
        "C": [(50, 50, 50), (90, 10, 10), (10, 90, 90)],
    }
    rep = R.analyze_randomisation(_make_ti2(tmp_path, strips))
    assert rep.safe is True
    assert rep.n_strips == 3


def test_analyze_unsafe_when_strips_identical(tmp_path: Path):
    # Two identical strips -> confusability 0 -> can't tell them apart.
    seq = [(100, 0, 0), (0, 100, 0), (0, 0, 100)]
    rep = R.analyze_randomisation(_make_ti2(tmp_path, {"A": seq, "B": list(seq)}))
    assert rep.safe is False
    assert rep.min_confusability < R._CONF_THRESHOLD


def test_analyze_unsafe_when_strip_is_palindrome(tmp_path: Path):
    # A strip that reads the same both ways -> direction can't be told apart.
    strips = {
        "A": [(20, 40, 60), (90, 90, 90), (20, 40, 60)],   # palindrome
        "B": [(0, 0, 0), (50, 0, 0), (100, 0, 0)],
    }
    rep = R.analyze_randomisation(_make_ti2(tmp_path, strips))
    assert rep.safe is False
    assert rep.min_symmetry < R._SYM_THRESHOLD


def test_analyze_trivially_safe_with_one_strip(tmp_path: Path):
    rep = R.analyze_randomisation(_make_ti2(tmp_path, {"A": [(1, 2, 3), (4, 5, 6)]}))
    assert rep.safe is True


def test_tag_rewrites_chart_id(tmp_path: Path):
    ti2 = _make_ti2(tmp_path, {"A": [(1, 2, 3)]}, kw="CHART_ID")
    assert R.tag_ti2_randomised(ti2) is True
    text = ti2.read_text(encoding="utf-8")
    assert "RANDOM_START" in text and "CHART_ID" not in text


def test_tag_is_idempotent_on_random_start(tmp_path: Path):
    ti2 = _make_ti2(tmp_path, {"A": [(1, 2, 3)]}, kw="RANDOM_START")
    assert R.tag_ti2_randomised(ti2) is False          # already randomised


def test_tag_missing_file_is_noop(tmp_path: Path):
    assert R.tag_ti2_randomised(tmp_path / "nope.ti2") is False


@argyll
@pytest.mark.parametrize("n", [100, 1500])
def test_analyze_flags_grid_unsafe_at_scale(tmp_path: Path, n):
    # An RGB-cube grid (i1Profiler-style) is fine when small but confusable once
    # it grows into many strips — the regression this whole feature guards.
    k = max(2, round(n ** (1 / 3)))
    grid = [(100 * r / (k - 1), 100 * g / (k - 1), 100 * b / (k - 1))
            for r in range(k) for g in range(k) for b in range(k)][:n]
    spec = R.ChartSpec.new("i1", "A4")
    res = R.regenerate(spec, grid, tmp_path, ARGYLL_BIN)
    rep = R.analyze_randomisation(res.ti2)
    if n >= 1500:
        assert rep.safe is False           # big structured grid -> unsafe


def test_instrument_and_paper_maps():
    assert R.instrument_to_flag("X-Rite ColorMunki") == "CM"
    assert R.instrument_to_flag("GretagMacbeth SpectroScan") == "SS"
    assert R.instrument_to_flag(None) == "i1"
    assert R.paper_to_flag(210.0, 297.0) == "A4"
    assert R.paper_to_flag(297.0, 210.0) == "A4R"
    assert R.paper_to_flag(123.0, 456.0) == "123x456"  # custom fallback


# --- LayoutOptions args ---------------------------------------------------
def test_layout_options_default_emits_nothing():
    # Defaults match printtarg's defaults — no flags should be emitted.
    assert R.LayoutOptions().to_printtarg_args() == []


def test_layout_options_margin_emits_both_m_and_M():
    args = R.LayoutOptions(margin_mm=5).to_printtarg_args()
    assert "-m5" in args
    assert "-M5" in args


def test_layout_options_bw_and_scales():
    args = R.LayoutOptions(
        spacer_mode="bw", patch_scale=1.3, spacer_scale=0.9,
        suppress_left_clip=True, no_strip_limit=True, double_density=True,
    ).to_printtarg_args()
    assert "-b" in args
    assert "-a1.30" in args
    assert "-A0.90" in args
    assert "-L" in args
    assert "-P" in args
    assert "-h" in args


# --- sibling .ti1 palette pickup ------------------------------------------
def test_loaded_chart_picks_up_sibling_density_extremes(ti2: Path, tmp_path: Path):
    # Write a .ti1 next to the .ti2 with a *non-default* extremes table; the
    # loader must pick it up so the editor restores the original palette
    # instead of resetting to printtarg's defaults.
    spec = R.ChartSpec.from_ti2(ti2)
    custom = ((100, 100, 100), (10, 20, 30), (40, 50, 60),
              (70, 80, 90), (5, 5, 5), (15, 25, 35),
              (45, 55, 65), (0, 0, 0))
    sibling = ti2.with_suffix(".ti1")
    R.write_ti1(spec, R.default_program(spec), sibling, spacer_palette=custom)
    reloaded = R.ChartSpec.from_ti2(ti2)
    assert reloaded.density_extremes is not None
    assert reloaded.density_extremes[1] == (10.0, 20.0, 30.0)
    assert reloaded.density_extremes[6] == (45.0, 55.0, 65.0)


# --- end-to-end patch geometry --------------------------------------------
@argyll
def test_patch_geometry_returns_a_rect_per_patch(tmp_path: Path):
    # Smoke-test: the geometry helper should produce one bbox per visible
    # patch on the page, with each rect fitting inside the chart image.
    spec = R.ChartSpec.new("i1", "A4")
    prog = R.seed_from_targen(ARGYLL_BIN, 50)
    res = R.regenerate(spec, prog, tmp_path, ARGYLL_BIN)
    geom = R.patch_geometry_for_page(
        res.ti2, res.tiffs[0], page=0, bw_tif_path=res.bw_tiffs[0])
    assert geom, "geometry should be non-empty"
    new_spec = R.ChartSpec.from_ti2(res.ti2)
    # Real (non-padding) patches each get a rect; printtarg fills any
    # partial last strip with sample_id=0 padding which the helper drops.
    real = [p for p in new_spec.patches if int(p.sample_id) > 0]
    assert len(geom) == len(real)
    arr = R._imread_rgb(res.tiffs[0])
    h, w = arr.shape[:2]
    for x0, y0, x1, y1 in geom.values():
        assert 0 <= x0 < x1 < w
        assert 0 <= y0 < y1 < h


def test_patch_geometry_requires_bw_twin():
    # Without the BW twin the helper bails out (returns {}) — callers must
    # opt in by passing the twin path. The signature default makes it easy
    # to forget; the smoke check protects against that.
    assert R.patch_geometry_for_page(Path("/no/such.ti2"),
                                      Path("/no/such.tif"), 0) == {}


# --- triple-density --------------------------------------------------------
@argyll
def test_triple_density_patches_target_instrument(tmp_path: Path):
    spec = R.ChartSpec.new("CM", "A4")
    prog = R.seed_from_targen(ARGYLL_BIN, 30)
    opts = R.LayoutOptions(triple_density=True, patch_scale=1.3,
                           margin_mm=5, suppress_left_clip=True,
                           no_strip_limit=True)
    res = R.regenerate(spec, prog, tmp_path, ARGYLL_BIN, options=opts)
    text = res.ti2.read_text(encoding="utf-8")
    assert 'TARGET_INSTRUMENT "X-Rite ColorMunki"' in text
    assert 'TARGET_INSTRUMENT "GretagMacbeth i1 Pro"' not in text


# --- .ti1 synthesis --------------------------------------------------------
def test_write_ti1_three_tables_and_order(ti2: Path, tmp_path: Path):
    spec = R.ChartSpec.from_ti2(ti2)
    dev_values = list(reversed(R.default_program(spec)))  # reverse order
    out = R.write_ti1(spec, dev_values, tmp_path / "c.ti1")
    text = out.read_text(encoding="utf-8")
    # printtarg requires three CGATS tables
    assert text.count("CTI1") == 3
    assert "DENSITY_EXTREME_VALUES" in text
    assert "DEVICE_COMBINATION_VALUES" in text
    # first data patch must be the source's last (order honoured)
    main = text.split("DENSITY_EXTREME_VALUES")[0]
    first_row = main.split("BEGIN_DATA\n")[1].splitlines()[0]
    assert first_row.split()[1:4] == ["0.0000", "0.0000", "100.0000"]


def test_write_ti1_recolours_a_patch(ti2: Path, tmp_path: Path):
    spec = R.ChartSpec.from_ti2(ti2)
    prog = R.default_program(spec)
    prog[0] = (12.0, 34.0, 56.0)  # recolour first patch
    out = R.write_ti1(spec, prog, tmp_path / "c.ti1")
    main = out.read_text(encoding="utf-8").split("DENSITY_EXTREME_VALUES")[0]
    first_row = main.split("BEGIN_DATA\n")[1].splitlines()[0]
    assert first_row.split()[1:4] == ["12.0000", "34.0000", "56.0000"]


def test_write_ti1_custom_palette_lands_in_extremes(ti2: Path, tmp_path: Path):
    spec = R.ChartSpec.from_ti2(ti2)
    pal = ((100, 100, 100), (30, 70, 100), (0, 0, 0))
    out = R.write_ti1(spec, R.default_program(spec), tmp_path / "c.ti1",
                      spacer_palette=pal)
    extremes = out.read_text(encoding="utf-8").split("DENSITY_EXTREME_VALUES")[1]
    assert 'DENSITY_EXTREME_VALUES "3"' in out.read_text(encoding="utf-8")
    assert "30.0000 70.0000 100.0000" in extremes


def test_write_ti1_non_rgb_routes_to_engine_format(tmp_path: Path):
    # Since #72 Tier A, non-RGB is no longer rejected: it routes to the
    # single-table engine writer (full coverage in test_ti2_relayout_nchannel).
    # Only the printtarg path (regenerate) still hard-fails on non-RGB.
    spec = R.ChartSpec(
        patches=[R.Patch("1", None, (0, 0, 0, 0), None)],
        dev_fields=["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"],
        has_xyz=False, color_rep="CMYK", white_point=None,
        instrument_flag="i1", paper_flag="A4", paper_mm=(210.0, 297.0),
    )
    out = R.write_ti1(spec, [(0, 0, 0, 0)], tmp_path / "c.ti1")
    assert 'COLOR_REP "CMYK"' in out.read_text(encoding="utf-8")
    with pytest.raises(RuntimeError, match="RGB charts only"):
        R.regenerate(spec, [(0, 0, 0, 0)], tmp_path, tmp_path)


# --- spacer segmentation + recolour (synthetic, no Argyll) -----------------
def test_segment_spacers_counts_components():
    mask = np.zeros((40, 40), dtype=bool)
    mask[5:9, 2:30] = True     # spacer 1
    mask[20:24, 2:30] = True   # spacer 2
    spacers = R.segment_spacers(mask, page=0)
    assert len(spacers) == 2
    areas = sorted(s.area for s in spacers)
    assert areas == [4 * 28, 4 * 28]
    assert all(s.page == 0 for s in spacers)


def test_recolor_only_touches_spacers(tmp_path: Path):
    import tifffile
    img = np.full((20, 20, 3), 200, dtype=np.uint8)
    src = tmp_path / "p.tif"
    tifffile.imwrite(str(src), img, photometric="rgb")
    mask = np.zeros((20, 20), dtype=bool)
    mask[5:8, 5:15] = True
    # min_extent=5 — the production default (20) rejects this tiny synthetic
    # spacer because real charts never have anything that small.
    spacers = R.segment_spacers(mask, page=0, min_extent=5)
    out = tmp_path / "p_rec.tif"
    R.recolor_spacers(src, spacers, (255, 0, 0), out)
    R.assert_patches_untouched(src, out, mask)
    after = np.asarray(__import__("PIL.Image", fromlist=["Image"]).open(out).convert("RGB"))
    assert tuple(after[6, 6]) == (255, 0, 0)      # spacer recoloured
    assert tuple(after[0, 0]) == (200, 200, 200)  # patch untouched


# --- end-to-end through printtarg ------------------------------------------
@argyll
def test_regenerate_roundtrip_and_palette(ti2: Path, tmp_path: Path):
    spec = R.ChartSpec.from_ti2(ti2)
    dev_values = list(reversed(R.default_program(spec)))
    pal = ((100, 100, 100), (30, 70, 100), (100, 70, 30), (70, 30, 100),
           (30, 100, 70), (100, 30, 70), (70, 100, 30), (0, 0, 0))
    res = R.regenerate(spec, dev_values, tmp_path, ARGYLL_BIN, spacer_palette=pal)
    R.assert_data_integrity(dev_values, res.ti2)
    assert len(res.tiffs) == len(res.bw_tiffs) >= 1
    mask = R.spacer_mask(res.tiffs[0], res.bw_tiffs[0])
    assert mask.sum() > 0
    spacers = R.segment_spacers(mask, page=0)
    assert len(spacers) > 0


@argyll
def test_recolour_patch_lands_in_regenerated_ti2(ti2: Path, tmp_path: Path):
    spec = R.ChartSpec.from_ti2(ti2)
    prog = R.default_program(spec)
    prog[2] = (20.0, 80.0, 75.0)  # recolour a patch to a custom teal
    res = R.regenerate(spec, prog, tmp_path, ARGYLL_BIN)
    R.assert_data_integrity(prog, res.ti2)  # the teal is present in the output
    new = R.ChartSpec.from_ti2(res.ti2)
    # printtarg snaps to 8-bit, so allow a tolerance of one code (~0.4/100).
    assert any(all(abs(a - b) <= 0.4 for a, b in zip(p.dev, (20.0, 80.0, 75.0)))
               for p in new.patches)


def test_engine_chart_reloads_in_sheet_order_renders_identically(tmp_path,
                                                                monkeypatch):
    """A randomised engine chart, reloaded into the editor (grid = .ti2 SHEET
    order), must re-render pixel-identically when treated as un-randomised — the
    grid already IS the randomised layout, so re-applying the seed would show a
    different chart than printed (#93)."""
    import random
    from workflow.layout_engine import chart as le_chart

    # The sheet carries a build date (chart.py stamps strftime("%Y-%m-%d") in
    # LOCAL time). This test renders the same chart twice and compares pixels,
    # so a run that straddles local midnight stamps two different dates and
    # fails — once a day, for no real reason. chart.py imports time inside the
    # function, so the stdlib module is the seam; other formats still delegate.
    import time as _t
    _real_strftime = _t.strftime
    monkeypatch.setattr(
        _t, "strftime",
        lambda fmt, *a: "2026-01-01" if fmt == "%Y-%m-%d"
        else _real_strftime(fmt, *a))
    from workflow.layout_engine.presets import default_recipe
    from PIL import Image

    src = R.ChartSpec.new("i1", "A4")
    random.seed(7)
    prog = [(random.random() * 100, random.random() * 100, random.random() * 100)
            for _ in range(200)]
    src_ti1 = tmp_path / "src.ti1"
    R.write_ti1(src, prog, src_ti1)

    # original chart, randomised with a fixed seed (like the Create Chart tab)
    rec = default_recipe("i1", "A4"); rec.randomize = True; rec.seed = 4242
    kw = rec.build_kwargs(); kw["dpi"] = 150
    # Same project on both so the notes strip (on by default; its profile name
    # comes from the output stem) doesn't make the pages differ — this test is
    # about patch-grid identity, not the notes content.
    kw["project"] = "Profile"
    orig = le_chart.build_chart(str(src_ti1), tmp_path / "orig", **kw)
    orig_img = np.asarray(Image.open(orig.tiff_paths[0]))

    # editor load: grid comes from the .ti2 in SAMPLE_LOC sheet order
    spec = R.ChartSpec.from_ti2(tmp_path / "orig.ti2")
    grid_ti1 = tmp_path / "grid.ti1"
    R.write_ti1(spec, R.default_program(spec), grid_ti1)

    # the editor renders the loaded grid un-randomised (the fix)
    rec2 = default_recipe("i1", "A4"); rec2.randomize = False
    kw2 = rec2.build_kwargs(); kw2["dpi"] = 150
    kw2["project"] = "Profile"
    reloaded = le_chart.build_chart(str(grid_ti1), tmp_path / "reload", **kw2)
    reload_img = np.asarray(Image.open(reloaded.tiff_paths[0]))

    assert np.array_equal(orig_img, reload_img)
    # and re-applying the seed on the sheet-order grid would NOT match (the bug)
    bad = le_chart.build_chart(str(grid_ti1), tmp_path / "bad", **kw)
    assert not np.array_equal(orig_img, np.asarray(Image.open(bad.tiff_paths[0])))


def test_load_colour_file_ti1_device_values(tmp_path):
    """Device-RGB CGATS (ti1) load via the existing loader, values preserved."""
    R.write_ti1(R.ChartSpec.new("i1", "A4"),
                [(100.0, 0.0, 0.0), (0.0, 50.0, 100.0)], tmp_path / "s.ti1")
    prog = R.load_colour_file(tmp_path / "s.ti1")
    assert (100.0, 0.0, 0.0) in [tuple(round(v, 3) for v in p) for p in prog]


def test_load_colour_file_plain_hex(tmp_path):
    p = tmp_path / "list.txt"; p.write_text("#ff0000\n#00ff00\n0,0,255\n", encoding="utf-8")
    prog = R.load_colour_file(p)
    assert len(prog) == 3


def test_load_colour_file_rejects_cie(tmp_path):
    """CIE reference files (XYZ/LAB only, no device values) are not supported —
    they raise a clear ValueError pointing the user elsewhere (#96)."""
    cie = ("NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\nSAMPLE_ID XYZ_X XYZ_Y XYZ_Z\n"
           "END_DATA_FORMAT\nBEGIN_DATA\nA1\t95\t100\t108\nA2\t0\t0\t0\n"
           "END_DATA\n")
    p = tmp_path / "ref.cie"; p.write_text(cie, encoding="utf-8")
    with pytest.raises(ValueError, match="CIE reference"):
        R.load_colour_file(p)
