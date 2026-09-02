"""The N-channel (CMY+N) profcheck: parsing, ΔE, and the output contract that
lets it drop into the existing Check & Refine pipeline unchanged."""
from __future__ import annotations

import numpy as np
import pytest

from workflow import profcheck_nchannel as pn
from workflow.profcheck_runner import (ProfcheckRunner, _ti3_device_channels,
                                       strips_to_refine)


def test_device_channels_detection(tmp_path):
    def ti3(rep):
        p = tmp_path / f"{rep}.ti3"
        p.write_text(f'CTI3\nCOLOR_REP "{rep}"\n', encoding="utf-8")
        return p
    assert _ti3_device_channels(ti3("CMYKOG_XYZ")) == 6
    assert _ti3_device_channels(ti3("CMYKOGV_XYZ")) == 7
    assert _ti3_device_channels(ti3("CMYK_XYZ")) == 4
    assert _ti3_device_channels(ti3("RGB_XYZ")) == 3


def test_device_part():
    assert pn.ti3_device_part("CMYKOG_XYZ") == "CMYKOG"
    assert pn.ti3_device_part("RGB_LAB") == "RGB"


def test_xyz_to_lab_white_is_neutral():
    lab = pn._xyz_to_lab(np.array([[96.420288, 100.0, 82.490540]]))
    assert abs(lab[0, 0] - 100.0) < 1e-3
    assert abs(lab[0, 1]) < 1e-3 and abs(lab[0, 2]) < 1e-3


def test_delta_e_formulas():
    a = np.array([[50.0, 10.0, 10.0]])
    b = np.array([[52.0, 12.0, 8.0]])
    assert abs(pn._delta_e(a, b, "")[0] - np.sqrt(4 + 4 + 4)) < 1e-9   # CIE76
    # identical colours -> 0 for every formula
    for f in ("", "-c", "-k"):
        assert pn._delta_e(a, a, f)[0] == pytest.approx(0.0, abs=1e-9)
    # CIE94 / CIEDE2000 shrink this particular difference vs CIE76
    assert pn._delta_e(a, b, "-c")[0] < pn._delta_e(a, b, "")[0]
    assert pn._delta_e(a, b, "-k")[0] < pn._delta_e(a, b, "")[0]


def test_read_ti3_nchannel_with_loc(tmp_path):
    p = tmp_path / "m.ti3"
    p.write_text(
        'CTI3\nDEVICE_CLASS "OUTPUT"\nCOLOR_REP "CMYKOG_XYZ"\n'
        "BEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC CMYKOG_C CMYKOG_M CMYKOG_Y CMYKOG_K CMYKOG_O "
        "CMYKOG_G XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n"
        "BEGIN_DATA\n"
        "1 A1 0 0 0 0 0 0 96.4 100 82.5\n"
        "2 B3 100 0 0 0 0 0 20 30 60\n"
        "END_DATA\n", encoding="utf-8")
    d = pn._read_ti3(p)
    assert d["n"] == 6 and not d["is_lab"]
    assert d["loc"] == ["A1", "B3"]
    assert d["device"].shape == (2, 6)
    assert d["device"][1, 0] == 100.0     # full cyan


def test_read_ti3_irgb_maps_to_rgb_fields(tmp_path):
    """iRGB / RGB / CMYK reps use fixed field names, not <REP>_<char>."""
    p = tmp_path / "m.ti3"
    p.write_text(
        'CTI3\nCOLOR_REP "iRGB_XYZ"\n'
        "BEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\nBEGIN_DATA\n"
        "1 100 100 100 96 100 82\nEND_DATA\n", encoding="utf-8")
    d = pn._read_ti3(p)
    assert d["n"] == 3            # RGB, not 4 chars of "iRGB"
    assert d["device"].shape == (1, 3)


def test_recompute_needs_spectral_data(tmp_path):
    """A non-default illuminant on a file without spectral data errors cleanly
    rather than silently using the file's D50 values."""
    p = tmp_path / "m.ti3"
    p.write_text(
        'CTI3\nCOLOR_REP "CMYKOG_XYZ"\n'
        "BEGIN_DATA_FORMAT\n"
        "SAMPLE_ID CMYKOG_C CMYKOG_M CMYKOG_Y CMYKOG_K CMYKOG_O CMYKOG_G "
        "XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\nBEGIN_DATA\n"
        "1 0 0 0 0 0 0 96 100 82\nEND_DATA\n", encoding="utf-8")
    with pytest.raises(pn.NChannelCheckError, match="spectral"):
        pn.run_check(p, p, bin_dir="/nonexistent", illum="D65")


def test_output_feeds_check_refine_pipeline():
    """A +N run's profcheck-format output must parse and flag strips exactly
    like real profcheck, so Check & Refine works unchanged."""
    log = "\n".join([
        "No of test patches = 3",
        "[3.500000] 7 @ C4: 0.5 0.5 0.5 0.1 0.2 0.3 -> 50.0 2.0 1.0 "
        "should be 47.0 3.0 2.0",
        "[2.100000] 2 @ C1: 0.1 0.1 0.1 0.0 0.0 0.0 -> 90.0 0.0 0.0 "
        "should be 88.0 1.0 1.0",
        "[0.400000] 5 @ A2: 0.0 0.0 0.0 0.0 0.0 0.0 -> 100.0 0.0 0.0 "
        "should be 100.0 0.0 0.0",
        "Profile check complete, errors: max. = 3.500000, avg. = 2.000000, "
        "RMS = 2.300000",
    ])
    runner = ProfcheckRunner(runner=None)
    res = runner.parse_results(log)
    assert res.peak_de == pytest.approx(3.5)
    assert res.avg_de == pytest.approx(2.0)
    # per-patch entries keyed by SAMPLE_LOC
    assert ("C4", 3.5) in res.patch_errors
    assert ("C1", 2.1) in res.patch_errors
    # strips with any patch over the 2.0 ΔE threshold are flagged (C only)
    flagged = dict(strips_to_refine(res.patch_errors, threshold=2.0))
    assert "C" in flagged and "A" not in flagged
