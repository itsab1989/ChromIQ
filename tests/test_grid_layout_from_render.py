"""Derive i1Profiler's dense-grid geometry from the charts it saved (#120).

These run against the real TIFFs i1Profiler produced from the ChromIQ layout
probe, committed under ``docs/i1profiler_probe/results/``. Every patch there is
painted a colour that encodes its own index (``scripts.make_i1profiler_probe``),
so a colour-verified cell also proves its patch was assigned correctly.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts.make_i1profiler_probe import encode
from workflow.grid_layout_from_render import (
    GridGeometryError, derive_grid_layout,
)

RESULTS = Path(__file__).resolve().parent.parent / "docs" / "i1profiler_probe" / "results"
PXF = RESULTS / "test1-autolayout.tif"                       # 600, 30x20, 8x7 mm
PWXF = RESULTS / "test2a-nolocations.tif"                    # 600, 40x15, 6x6 mm
MULTI = [RESULTS / "multipage" / "ChromIQ i1Profiler layo_1_2.tif",
         RESULTS / "multipage" / "ChromIQ i1Profiler layo_2_2.tif"]  # 1500, 30x50, 2pp

pytestmark = pytest.mark.skipif(
    not PXF.is_file(), reason="probe result TIFFs not present")


def _rgb100(n: int) -> np.ndarray:
    """The probe patch list as device RGB 0..100, in fill order."""
    return np.array([[c / 255 * 100 for c in encode(i)] for i in range(n)])


def _mm(layout: dict, patch: dict, key: str) -> float:
    return patch[key] * 25.4 / layout["dpi"]


def test_single_page_pxf_grid():
    lay = derive_grid_layout([PXF], _rgb100(600))
    assert lay["engine"] == "derived"
    assert len(lay["patches"]) == 600
    assert {p["page"] for p in lay["patches"]} == {0}
    assert lay["paper_mm"] == [271.0, 175.0]
    p0 = lay["patches"][0]
    assert p0["loc"] == "1"
    assert _mm(lay, p0, "w") == pytest.approx(8.0, abs=0.1)
    assert _mm(lay, p0, "h") == pytest.approx(7.0, abs=0.1)
    assert _mm(lay, p0, "x") == pytest.approx(15.5, abs=0.2)
    assert _mm(lay, p0, "y") == pytest.approx(24.5, abs=0.2)


def test_single_page_pwxf_smaller_patches():
    # 40 columns x 15 rows of 6x6 mm — the column boundaries are invisible to
    # edge detection on this probe (neighbours 15 apart, 15 == -1 mod 16), so
    # this only passes via the colour-verified column SEARCH.
    lay = derive_grid_layout([PWXF], _rgb100(600))
    assert len(lay["patches"]) == 600
    p0 = lay["patches"][0]
    assert _mm(lay, p0, "w") == pytest.approx(6.0, abs=0.1)
    assert _mm(lay, p0, "h") == pytest.approx(6.0, abs=0.1)


def test_multipage_column_major_split():
    lay = derive_grid_layout(MULTI, _rgb100(1500))
    assert len(lay["patches"]) == 1500
    by_loc = {p["loc"]: p for p in lay["patches"]}
    # #120 rule: 30 cols x 50 rows, column-major, split into two 25-row pages.
    # patch index i -> col=i//50, row_global=i%50, page=row_global//25.
    for i in (0, 24, 25, 49, 50, 749, 750, 1499):
        p = by_loc[str(i + 1)]
        assert p["page"] == (i % 50) // 25, f"patch {i+1} on wrong page"
    assert {p["page"] for p in lay["patches"]} == {0, 1}
    assert sum(p["page"] == 0 for p in lay["patches"]) == 750


def test_custom_locs_are_honoured():
    locs = [f"P{i:04d}" for i in range(600)]
    lay = derive_grid_layout([PXF], _rgb100(600), locs=locs)
    assert lay["patches"][0]["loc"] == "P0000"
    assert {p["loc"] for p in lay["patches"]} == set(locs)


def test_shuffled_patch_set_is_refused():
    shuffled = _rgb100(600)
    np.random.default_rng(0).shuffle(shuffled)
    with pytest.raises(GridGeometryError):
        derive_grid_layout([PXF], shuffled)


def test_wrong_patch_count_is_refused():
    with pytest.raises(GridGeometryError):
        derive_grid_layout([PXF], _rgb100(599))


def test_missing_page_is_refused():
    # 1500 patches need two pages; offering only one cannot cover the chart.
    with pytest.raises(GridGeometryError):
        derive_grid_layout([MULTI[0]], _rgb100(1500))


def test_feeds_scanin_target_end_to_end(tmp_path):
    from workflow.scanin_target import build_scanin_target_from_paths

    lay = derive_grid_layout(MULTI, _rgb100(1500))
    (tmp_path / "c.channels.json").write_text(json.dumps({"layout": lay}), encoding="utf-8")
    rows = []
    for i in range(1500):
        r, g, b = encode(i)
        rows.append(f"{i+1} {i+1} {r/2.55:.3f} {g/2.55:.3f} {b/2.55:.3f} 50 50 50")
    (tmp_path / "m.ti3").write_text(
        'CTI3\n\nKEYWORD "SAMPLE_LOC"\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\nNUMBER_OF_SETS 1500\nBEGIN_DATA\n"
        + "\n".join(rows) + "\nEND_DATA\n", encoding="utf-8")
    res = build_scanin_target_from_paths(
        tmp_path / "c.channels.json", tmp_path / "m.ti3", tmp_path / "out")
    assert res.n_patches == 1500 and res.n_pages == 2
    assert [p.name for p in res.cht_paths] == ["out_01.cht", "out_02.cht"]
    # numeric SampleID locs (what txt2ti3 yields) join the numeric geometry locs
    page1_boxes = [ln for ln in res.cht_paths[0].read_text(encoding="utf-8").splitlines()
                   if ln.strip().startswith("X ")]
    assert len(page1_boxes) == 750


def _numeric_ti3(path: Path, n: int) -> None:
    """A measurement whose SAMPLE_LOC is the patch number 1…N — what txt2ti3
    writes from an i1Profiler measurement."""
    rows = []
    for i in range(n):
        r, g, b = encode(i)
        rows.append(f"{i+1} {i+1} {r/2.55:.3f} {g/2.55:.3f} {b/2.55:.3f} 50 50 50")
    path.write_text(
        'CTI3\n\nKEYWORD "SAMPLE_LOC"\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\n" + f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n"
        + "\n".join(rows) + "\nEND_DATA\n", encoding="utf-8")


def test_orchestrator_from_ti1_and_render(tmp_path):
    """The full #120 path: patch set (.ti1) + saved TIFF(s) + numeric-loc .ti3
    → channels.json + per-page .cht + .cie."""
    from scripts.make_i1profiler_probe import write_ti1
    from workflow.scanin_target import (
        ScaninTargetError, build_scanin_target_from_render,
    )

    ti1 = tmp_path / "probe.ti1"
    write_ti1(ti1, 1500)
    _numeric_ti3(tmp_path / "m.ti3", 1500)
    res = build_scanin_target_from_render(
        ti1, MULTI, tmp_path / "m.ti3", tmp_path / "chart")
    assert res.n_patches == 1500 and res.n_pages == 2
    assert (tmp_path / "chart.channels.json").is_file()
    assert [p.name for p in res.cht_paths] == ["chart_01.cht", "chart_02.cht"]

    # Wrong page set for this patch count is refused (as a ScaninTargetError).
    with pytest.raises(ScaninTargetError):
        build_scanin_target_from_render(
            ti1, [MULTI[0]], tmp_path / "m.ti3", tmp_path / "bad")
