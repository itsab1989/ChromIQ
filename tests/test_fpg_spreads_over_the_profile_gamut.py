"""A FROM PROFILE GAMUT chart is spread over the PROFILE's gamut (Knut, #182
6096108924, 4.3.4 beta 1).

Knut saw "large holes in the distribution" of the 324-patch verification chart
built From Profile Gamut on his run 5. Measured on his profile: most of what
the 3D view shows is the view (it plots device RGB, where a perceptually even
set looks uneven; the biggest device-space gap, 35 device units in the blues,
is 7.3 dE76 from the nearest patch), but part is real. The chart's body was
the first reachable colours in master order, which are well spread over sRGB,
where the master was cut, and know nothing of where this printer's gamut ends:
the largest empty places sat on the gamut's outer shell, up to 16.1 dE76 from
the nearest patch at 324 patches and 23.7 at 100. The body is now picked by a
farthest-point pass over the reachable colours, seeded with the corners as
printed and with white and black: 10.6 and 14.9.

The covering radius used here is the largest distance from any reachable
master colour to the nearest patch of the chart: the biggest hole a
verification can have inside what the master can offer.
"""
from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from workflow import gamut_target as gt
import workflow.xicclu_runner as xr

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PROFILE = (ROOT / "tests/data/g_basti_et8550_run1_verify/"
                   "ET8550_EpsPremSG_AdobeRGB_CM_Okt26.icc")


# --- a stand-in printer: a gamut smaller than sRGB, shifted off-centre ------

def _inside(lab) -> bool:
    L, a, b = lab
    return 20.0 <= L <= 92.0 and math.hypot(a - 5.0, b + 10.0) <= 45.0


def _clip(lab):
    L, a, b = lab
    L = min(92.0, max(20.0, L))
    da, db = a - 5.0, b + 10.0
    c = math.hypot(da, db)
    if c > 45.0:
        da, db = da * 45.0 / c, db * 45.0 / c
    return (L, 5.0 + da, -10.0 + db)


def _enc(lab):
    return (lab[0], (lab[1] + 128.0) / 2.56, (lab[2] + 128.0) / 2.56)


def _dec(dev):
    return (dev[0], dev[1] * 2.56 - 128.0, dev[2] * 2.56 - 128.0)


@pytest.fixture
def stand_in_printer(monkeypatch, tmp_path):
    """xicclu replaced by an exact profile of the stand-in gamut: inside it
    the round trip is exact, outside it the colour is clipped to the
    surface (so it moves far and is not reachable)."""
    monkeypatch.setattr(xr, "backward_device",
                        lambda labs, *a, **k: [_enc(_clip(l)) for l in labs])
    monkeypatch.setattr(xr, "forward_lab",
                        lambda devs, *a, **k: [_dec(d) for d in devs])
    gt.clear_round_trip_cache()
    profile = tmp_path / "stand-in.icc"
    profile.write_bytes(b"icc")
    yield profile
    gt.clear_round_trip_cache()


def _select(profile, count, margin=gt.MARGIN_FULL, **kw):
    return gt.select_gamut_targets(profile, count, margin, gt.INTENT_ABSOLUTE,
                                   **kw)


def _covering_radius(reachable, chart_labs) -> float:
    r = np.asarray(reachable, float)
    c = np.asarray(chart_labs, float)
    return float(np.min(np.linalg.norm(r[:, None, :] - c[None], axis=2),
                        axis=1).max())


def test_a_small_chart_leaves_no_big_hole_in_the_gamut(stand_in_printer):
    """THE CATCH. Taking the first reachable colours in master order left a
    hole of 26.2 dE76 in this gamut at 100 patches; spread over the gamut
    it is 16.0."""
    reachable = [l for l in gt.load_master_labs() if _inside(l)]
    sel = _select(stand_in_printer, 100, bin_dir="/nowhere")
    chart = [lab for _i, lab, _dev in sel.targets]
    chart += [_dec(dev) for dev, _lab in sel.corners]
    radius = _covering_radius(reachable, chart)
    assert radius <= 18.0, (
        f"a reachable colour is {radius:.1f} dE76 from the nearest patch")


def test_the_same_profile_and_count_give_the_same_chart(stand_in_printer):
    a = _select(stand_in_printer, 150, bin_dir="/nowhere")
    gt.clear_round_trip_cache()
    b = _select(stand_in_printer, 150, bin_dir="/nowhere")
    assert [t[0] for t in a.targets] == [t[0] for t in b.targets]
    assert [t[2] for t in a.targets] == [t[2] for t in b.targets]


def test_a_smaller_chart_is_inside_a_larger_one(stand_in_printer):
    ids = [{t[0] for t in _select(stand_in_printer, n,
                                  bin_dir="/nowhere").targets}
           for n in (40, 100, 316, 600)]
    for small, large in zip(ids, ids[1:]):
        assert small <= large


def test_the_eight_corners_are_always_there_and_last(stand_in_printer):
    for n in (10, 100, 316):
        sel = _select(stand_in_printer, n, bin_dir="/nowhere")
        assert [dev for dev, _lab in sel.corners] == list(gt.CORNER_DEVICES)
        rows = gt.reference_rows(sel)
        assert [dev for _sid, dev, _lab in rows[-8:]] == list(gt.CORNER_DEVICES)
        assert gt.corner_sample_ids(sel) == list(range(n + 1, n + 9))


def test_the_spread_order_is_a_prefix_order_and_keeps_away_from_seeds():
    pts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (10.0, 0.0, 0.0),
           (20.0, 0.0, 0.0), (20.0, 0.0, 0.0)]
    cands = [0, 1, 2, 3, 4]
    full = gt._farthest_point_order(pts, cands, [(0.0, 0.0, 0.0)], 5)
    # Furthest from the seed first, the tie (3 and 4 are the same colour)
    # going to the earlier one; then whatever is furthest from everything
    # taken; the two colours with nothing left between them come last,
    # earlier first.
    assert full == [3, 2, 1, 0, 4]
    for k in range(1, 6):
        assert gt._farthest_point_order(pts, cands, [(0.0, 0.0, 0.0)],
                                        k) == full[:k]


@pytest.mark.skipif(shutil.which("xicclu") is None
                    and not Path("/Applications/Argyll/bin/xicclu").exists(),
                    reason="needs ArgyllCMS xicclu")
def test_a_real_profile_chart_leaves_no_big_hole(tmp_path):
    """Through a real printer profile (the presets' certificate profile),
    margin "safe": master order left 29.7 dE76 at 100 patches; spread, 21.2.
    Measured with the corners and every reachable master colour."""
    from core.resource_path import argyll_binary
    xicclu = shutil.which("xicclu") or argyll_binary("xicclu")
    bin_dir = str(Path(xicclu).parent)
    prof = tmp_path / FIXTURE_PROFILE.name
    shutil.copy(FIXTURE_PROFILE, prof)
    gt.clear_round_trip_cache()
    try:
        labs = gt.load_master_labs()
        dev, back = gt._round_trip(labs, prof, bin_dir, "a", subprocess.run)
        thr = gt.MARGIN_THRESHOLD_DE76[gt.MARGIN_SAFE]
        reachable = [back[i] for i in range(len(labs))
                     if math.dist(labs[i], back[i]) <= thr
                     and gt.device_is_printable(dev[i])]
        sel = _select(prof, 100, gt.MARGIN_SAFE, bin_dir=bin_dir)
        chart = [back[t[0]] for t in sel.targets]
        chart += xr.forward_lab(list(gt.CORNER_DEVICES), prof, bin_dir,
                                intent="a")
        radius = _covering_radius(reachable, chart)
    finally:
        gt.clear_round_trip_cache()
    assert radius <= 24.0, (
        f"a reachable colour is {radius:.1f} dE76 from the nearest patch")
