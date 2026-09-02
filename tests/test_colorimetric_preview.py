"""Colorimetric preview of device-native charts via cctiff (#72 Tier D).

Unit tests use an injectable runner; the live test renders a real CMYK
separated TIFF through Apple's Generic CMYK profile and checks the preview
pipeline picks the true-colour path and badges it.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.argyll_env import argyll_bin_dir, argyll_tool
from workflow import colorimetric_preview as CP

ARGYLL_BIN = argyll_bin_dir()
GENERIC_CMYK = Path("/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc")
live = pytest.mark.skipif(
    argyll_tool("cctiff") is None or not GENERIC_CMYK.exists(),
    reason="ArgyllCMS or Generic CMYK profile not installed")


def test_find_profile_prefers_preconditioning_icc(tmp_path):
    tif = tmp_path / "chart_01.tif"
    tif.touch()
    assert CP.find_device_profile(tif) is None
    (tmp_path / "meta.json").write_text(json.dumps(
        {"editor_recipe": {"device": {"precond": str(GENERIC_CMYK)}}}), encoding="utf-8")
    if GENERIC_CMYK.exists():
        assert CP.find_device_profile(tif) == GENERIC_CMYK
    pre = tmp_path / "preconditioning.icc"
    pre.touch()
    assert CP.find_device_profile(tif) == pre     # run artefact wins


def test_conversion_failure_returns_none(tmp_path):
    tif = tmp_path / "c.tif"
    tif.write_bytes(b"x")
    prof = tmp_path / "p.icc"
    prof.write_bytes(b"x")

    def boom(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="nope")

    assert CP.colorimetric_rgb_tiff(tif, prof, ARGYLL_BIN, runner=boom) is None
    assert CP.colorimetric_rgb_tiff(tmp_path / "missing.tif", prof,
                                    ARGYLL_BIN) is None


@live
def test_live_cmyk_chart_gets_true_colour_preview(tmp_path):
    # Build a real separated CMYK chart page with the engine, put the profile
    # where discovery finds it, and load through the actual preview pipeline.
    import numpy as np
    import workflow.ti2_relayout as R
    from workflow.layout_engine import chart as eng_chart

    rows = [((0.0, 0.0, 0.0, 0.0), None), ((100.0, 0.0, 0.0, 0.0), None),
            ((0.0, 100.0, 0.0, 0.0), None), ((0.0, 0.0, 0.0, 100.0), None)]
    ti1 = R.write_ti1_nchannel("CMYK", ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"],
                               rows, tmp_path / "c.ti1")
    res = eng_chart.build_chart(str(ti1), tmp_path / "c", seed=1, dpi=72)
    tif = (res.tiff_paths or [None])[0]
    assert tif is not None
    import shutil
    shutil.copy(GENERIC_CMYK, tmp_path / "preconditioning.icc")

    conv = CP.colorimetric_rgb_tiff(tif, tmp_path / "preconditioning.icc",
                                    ARGYLL_BIN)
    assert conv is not None and conv.is_file()
    # Cache hit: same object for a second call.
    assert CP.colorimetric_rgb_tiff(tif, tmp_path / "preconditioning.icc",
                                    ARGYLL_BIN) == conv

    pytest.importorskip("PyQt6")
    from ui import tiff_preview as TP
    img = TP.load_tiff_as_rgb(tif, 0)
    assert img.mode == "RGB"
    assert TP.last_render_mode() == "profile"     # true colours + badge
    # Without the profile: the approximate composite, honestly badged.
    (tmp_path / "preconditioning.icc").unlink()
    CP._cache.clear()
    img2 = TP.load_tiff_as_rgb(tif, 0)
    assert TP.last_render_mode() == "approx"
    # And the two renders genuinely differ (proof the transform ran).
    assert np.asarray(img).shape == np.asarray(img2).shape
    assert not np.array_equal(np.asarray(img), np.asarray(img2))
