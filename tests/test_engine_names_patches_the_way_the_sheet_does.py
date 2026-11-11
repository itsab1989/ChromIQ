"""The engine talks about patches the way the printed sheet does.

Two things the engine-accuracy challenge found on 2026-09-04:

* The accurate mode's "please remeasure" line named DATA ROWS ("rows 757,
  811"). On a targen chart that coincides with the SAMPLE_ID, but the sheet
  labels its patches by SAMPLE_LOC (F20, W1), and on an imported or merged
  chart the row number points at the wrong patch altogether. The message now
  names the location the person can find.
* A ``nan``/``inf`` reading (scanin writes them for a patch with no usable
  pixels; a stuck instrument can too) reached the fit and died with
  ``ValueError: cannot convert float NaN to integer``. The reader now refuses
  the file with a message naming the patches, before any maths runs.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from tests.test_profile_engine import synth_xyz
from workflow.profile_engine import BuildSettings, build_profile
from workflow.profile_engine.ti3_data import Ti3Error, read_ti3


def _write(path: Path, dev: np.ndarray, xyz: np.ndarray, *,
           locs: bool = True, ids_offset: int = 0,
           poison: dict[int, str] | None = None) -> Path:
    lines = ["CTI3", "", 'DESCRIPTOR "synthetic"', 'COLOR_REP "RGB_XYZ"',
             f"NUMBER_OF_FIELDS {8 if locs else 7}", "BEGIN_DATA_FORMAT",
             ("SAMPLE_ID SAMPLE_LOC " if locs else "SAMPLE_ID ")
             + "RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(dev)}", "BEGIN_DATA"]
    for i, (d, x) in enumerate(zip(dev, xyz)):
        loc = f'"{chr(65 + i // 26)}{i % 26 + 1}" ' if locs else ""
        vals = [f"{v * 100:.4f}" for v in d] + [f"{v:.4f}" for v in x]
        if poison and i in poison:
            vals[3] = poison[i]
        lines.append(f"{i + 1 + ids_offset} {loc}" + " ".join(vals))
    lines.append("END_DATA")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _chart(n: int = 300, seed: int = 9):
    rng = np.random.default_rng(seed)
    dev = rng.uniform(0.0, 1.0, (n, 3))
    dev[0] = 1.0                                # a device white
    dev[1] = 0.0
    return dev, synth_xyz(dev, additive=True)


def test_patch_label_prefers_the_sheet_location(tmp_path):
    dev, xyz = _chart(30)
    m = read_ti3(_write(tmp_path / "a.ti3", dev, xyz, ids_offset=1000))
    assert m.sample_locs is not None and m.sample_ids is not None
    assert m.patch_label(0) == "A1 (ID 1001)"
    assert m.patch_label(27) == "B2 (ID 1028)"
    m2 = read_ti3(_write(tmp_path / "b.ti3", dev, xyz, locs=False))
    assert m2.sample_locs is None
    assert m2.patch_label(5) == "6"


def test_nan_reading_is_refused_naming_the_patch(tmp_path):
    dev, xyz = _chart(30)
    bad = _write(tmp_path / "nan.ti3", dev, xyz,
                 poison={7: "nan", 12: "inf"})
    with pytest.raises(Ti3Error) as exc:
        read_ti3(bad)
    msg = str(exc.value)
    assert "2 patch(es)" in msg and "A8 (ID 8)" in msg and "A13 (ID 13)" in msg
    assert "Re-measure" in msg
    # …and the builder surfaces exactly that text, not a numpy error.
    with pytest.raises(Ti3Error, match="A8"):
        build_profile(bad, tmp_path / "nan.icc",
                      BuildSettings(quality="l", gammap_mode="accurate"))


def test_outlier_line_names_the_sheet_location(tmp_path):
    dev, xyz = _chart(300)
    xyz_bad = xyz.copy()
    xyz_bad[123] *= np.array([0.45, 0.55, 0.40])        # a smudged patch
    ti3 = _write(tmp_path / "s.ti3", dev, xyz_bad, ids_offset=5000)
    lines: list[str] = []
    res = build_profile(ti3, tmp_path / "s.icc",
                        BuildSettings(quality="l", gammap_mode="accurate",
                                      progress=lines.append))
    assert 123 in res.outlier_rows
    said = [ln for ln in lines if "disagree strongly" in ln]
    assert said, lines
    # Row 123 (0-based) is sheet cell E20 — chr(65 + 123 // 26) = 'E',
    # 123 % 26 + 1 = 20 — and carries SAMPLE_ID 5124. The line must name
    # the cell, and must not fall back to a bare data-row number.
    assert "E20 (ID 5124)" in said[0], said[0]
    assert "rows 124" not in said[0] and "row 124" not in said[0]
