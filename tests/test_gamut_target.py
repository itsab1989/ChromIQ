"""#133 feature B — the gamut-target engine and the report's third reference.

Covers: nested-order selection with the margin thresholds, the unconditional
§9a corners, the chart/reference writers agreeing on SAMPLE_ID order, the
report's ``colorimetric`` reference source, the §9.1 refusal (no silent sRGB
fallback), and the corner exclusion from the accuracy statistics.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow import gamut_target as gt


# A tiny master set: 5 colours, no APPROX_WHITE_POINT (so no D65 adaptation),
# XYZ chosen to be distinct.
_MASTER = """CTI1

DESCRIPTOR "test master"
ORIGINATOR "ChromIQ"
COLOR_REP "iRGB"

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 5
BEGIN_DATA
1 100 100 100 96.42 100.0 82.53
2 0 0 0 1.0 1.0 0.8
3 100 0 0 41.0 21.0 2.0
4 0 100 0 35.0 70.0 11.0
5 0 0 100 18.0 9.0 95.0
END_DATA
"""


@pytest.fixture
def master(tmp_path: Path) -> Path:
    p = tmp_path / "master.ti1"
    p.write_text(_MASTER)
    return p


def _stub_xicclu(monkeypatch, moved: "dict[int, float]"):
    """Round-trip stub: backward returns a marker device value per row;
    forward returns the input Lab shifted by ``moved[i]`` ΔE76 for row i."""
    def backward(labs, profile, bin_dir, **kw):
        return [(float(i), float(i), float(i)) for i in range(len(labs))]

    def forward(devs, profile, bin_dir, **kw):
        out = []
        for dev in devs:
            i = int(dev[0])
            lab = _stub_xicclu.labs[i]
            out.append((lab[0] + moved.get(i, 0.0), lab[1], lab[2]))
        return out

    import workflow.xicclu_runner as xr
    monkeypatch.setattr(xr, "backward_device", backward)
    monkeypatch.setattr(xr, "forward_lab", forward)
    return backward, forward


def test_selection_is_nested_capped_and_margin_aware(tmp_path, master, monkeypatch):
    labs = gt.load_master_labs(master)
    _stub_xicclu.labs = labs
    # Rows 1 and 3 move far (clipped); the rest round-trip cleanly.
    _stub_xicclu(monkeypatch, {1: 10.0, 3: 2.0})
    profile = tmp_path / "p.icc"
    profile.write_bytes(b"icc")

    sel = gt.select_gamut_targets(profile, 2, gt.MARGIN_SAFE, gt.INTENT_ABSOLUTE,
                                  bin_dir="/nowhere", master_path=master)
    # safe threshold 1.5: rows 0, 2, 4 are in gamut (row 3 moved 2.0 > 1.5).
    assert sel.in_gamut_total == 3
    assert [t[0] for t in sel.targets] == [0, 2]          # nested order, capped
    assert len(sel.corners) == 8                          # §9a: unconditional

    sel_full = gt.select_gamut_targets(profile, 10, gt.MARGIN_FULL,
                                       gt.INTENT_ABSOLUTE, bin_dir="/nowhere",
                                       master_path=master)
    # full threshold 3.0 admits row 3 too; the cap is honest (only 4 exist).
    assert sel_full.in_gamut_total == 4
    assert sel_full.achieved == 4
    assert sel_full.requested == 10


def test_chart_and_reference_agree_on_sample_ids(tmp_path, master, monkeypatch):
    labs = gt.load_master_labs(master)
    _stub_xicclu.labs = labs
    _stub_xicclu(monkeypatch, {})
    profile = tmp_path / "p.icc"
    profile.write_bytes(b"icc")
    sel = gt.select_gamut_targets(profile, 3, gt.MARGIN_SAFE, gt.INTENT_ABSOLUTE,
                                  bin_dir="/nowhere", master_path=master)
    ti1 = gt.write_gamut_ti1(sel, tmp_path / "chart.ti1")
    ref = gt.write_colorimetric_reference(sel, tmp_path / "chart-reference.ti3")
    back = gt.read_colorimetric_reference(ref)

    # 3 targets + 8 corners, ids 1..11; corners are ids 4..11.
    assert len(back["labs"]) == 11
    assert back["corner_ids"] == {str(i) for i in range(4, 12)}
    assert back["set_version"] == gt.MASTER_SET_VERSION
    # The ti1 holds the same patches in the same order.
    from workflow.ti3_analysis import parse_ti3
    chart = parse_ti3(ti1)
    assert chart.n_patches == 11
    # Reference row 1's Lab is the first master target's Lab.
    assert back["labs"]["1"] == pytest.approx(sel.targets[0][1], abs=0.02)


def test_reference_reader_survives_a_missing_or_broken_file(tmp_path):
    assert gt.read_colorimetric_reference(tmp_path / "gone.ti3") is None
    broken = tmp_path / "broken.ti3"
    broken.write_text("not a cgats file at all")
    assert gt.read_colorimetric_reference(broken) is None


def test_mark_chart_records_the_reference_in_the_sidecar(tmp_path):
    ti2 = tmp_path / "P-verify.ti2"
    ti2.write_text("CTI2\n")
    gt.mark_chart_as_colorimetric(ti2, tmp_path / "P-verify-reference.ti3")
    data = json.loads((tmp_path / "P-verify.channels.json").read_text())
    assert data["colorimetric_reference"] == "P-verify-reference.ti3"
    # And feature A's detection reads it as the A3c claim.
    from workflow.verification_print import (STATE_CONVERTED_REF_MISSING,
                                             chart_conversion_state)
    assert chart_conversion_state(ti2) == STATE_CONVERTED_REF_MISSING


# ---------------------------------------------------------------- the report
_TI3 = """CTI3

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 3
BEGIN_DATA
1 "A1" 50 60 70 30.0 32.0 30.0
2 "A2" 20 30 40 8.0 9.0 10.0
3 "A3" 100 100 100 96.42 100.0 82.53
END_DATA
"""

_TI2 = _TI3.replace("CTI3", "CTI1")


def _fake_selection() -> gt.GamutSelection:
    """Two targets (ids 1, 2) + one 'corner' (id 3) — small on purpose."""
    sel = gt.GamutSelection(
        master_version="TEST-r0", master_total=5, in_gamut_total=2,
        requested=2, intent="absolute", margin="safe")
    from workflow.ti3_analysis import xyz_to_lab
    sel.targets = [
        (0, xyz_to_lab((0.30, 0.32, 0.30)), (50.0, 60.0, 70.0)),
        (1, xyz_to_lab((0.08, 0.09, 0.10)), (20.0, 30.0, 40.0)),
    ]
    sel.corners = [((100.0, 100.0, 100.0),
                    xyz_to_lab((0.9642, 1.0, 0.8253)))]
    return sel


def test_report_uses_the_colorimetric_reference_and_excludes_corners(tmp_path):
    from workflow.measurement_report import build_report
    (tmp_path / "c.ti2").write_text(_TI2)
    (tmp_path / "c.ti3").write_text(_TI3)
    gt.write_colorimetric_reference(_fake_selection(),
                                    tmp_path / "c-reference.ti3")
    r = build_report(tmp_path / "c.ti3")
    assert r["reference_source"] == "colorimetric"
    assert r["colorimetric"]["set_version"] == "TEST-r0"
    # §9a rule 2: id 3 is a corner → the statistics cover only the 2 targets.
    assert r["de00"]["n"] == 2
    # The measurement matches the reference exactly → ΔE ≈ 0.
    assert r["de00"]["max"] < 0.05
    assert all(w["loc"] != "A3" for w in r.get("worst_patches", []))


def test_report_refuses_when_the_reference_is_claimed_but_missing(tmp_path):
    """§9.1 / B6 — never a plausible number from the wrong yardstick."""
    from workflow.measurement_report import build_report
    (tmp_path / "c.ti2").write_text(_TI2)
    (tmp_path / "c.ti3").write_text(_TI3)
    (tmp_path / "c.channels.json").write_text(json.dumps(
        {"colorimetric_reference": "c-reference.ti3"}))
    r = build_report(tmp_path / "c.ti3")
    assert r["reference_source"] == "colorimetric-missing"
    assert "de00" not in r
    # The corners section may exist (device values are real), but nothing may
    # carry an expected colour computed from the wrong reference.
    for c in r.get("corners", []):
        assert "de" not in c


def test_plain_charts_are_untouched(tmp_path):
    from workflow.measurement_report import build_report
    (tmp_path / "c.ti2").write_text(_TI2)
    (tmp_path / "c.ti3").write_text(_TI3)
    r = build_report(tmp_path / "c.ti3")
    assert r["reference_source"] == "design"
    assert r["de00"]["n"] == 3
