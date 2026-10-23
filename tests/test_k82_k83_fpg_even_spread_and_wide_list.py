"""FROM PROFILE GAMUT, 4.3.5: a wider candidate list (k83) and an even spread
over the profile's whole gamut volume (k82).

Knut, #182 6102031563, agreed by Sebastian 2026-10-11:

* k83, the list: "That list of colors should contain colors that any
  professional printer may achieve. That possibly means even larger than
  AdobeRGB1998 [...] a whole cube of 22x22x22 (10648 colors)". The r1 list
  was sampled in sRGB only, and about a fifth of an Epson ET-8550 glossy
  profile's gamut lies outside sRGB: on that profile 4.3.4 left places 35.7
  dE76 from the nearest patch of a 324-patch chart.
* k82, the spread: "spread evenly out for the whole gamut volume, so that the
  chosen numbers follow the profiles shape and spreads evenly out filling all
  gaps, and all colors having the same distance from each other [...] less
  number of colors, the distance between each color would be larger [...]
  For the 324 patch chart, that would be 316+8 cube corners."

Measured on the same profile at 324 patches (report folder
2026-10-11_435_fpg_verify/k83, eval_impl.txt), 4.3.4 against 4.3.5: closest
pair 2.90 against 11.24 dE76, median nearest neighbour 11.59 against 12.63,
largest empty place in the gamut 35.70 against 14.41.
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
ET8550 = (ROOT / "tests/data/g_basti_et8550_run1_verify/"
          "ET8550_EpsPremSG_AdobeRGB_CM_Okt26.icc")


def _bin_dir() -> str:
    from core.resource_path import argyll_binary
    xicclu = shutil.which("xicclu") or argyll_binary("xicclu")
    if not xicclu or not Path(xicclu).exists():
        pytest.skip("needs ArgyllCMS xicclu")
    return str(Path(xicclu).parent)


# --- k83: the list ---------------------------------------------------------

def _adobe_rgb_primaries_d50():
    """Adobe RGB (1998)'s and sRGB's primaries as XYZ D50 (Bradford)."""
    def m(prim, white):
        cols = np.array([[x / y, 1.0, (1 - x - y) / y] for x, y in prim]).T
        return cols * np.linalg.solve(cols, white)
    d65 = np.array([0.95047, 1.0, 1.08883])
    brad = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367],
                     [0.0389, -0.0685, 1.0296]])
    d50 = np.array(gt._D50_WHITE)
    adapt = np.linalg.inv(brad) @ np.diag((brad @ d50) / (brad @ d65)) @ brad
    out = {}
    for name, prim in (("Adobe RGB", ((0.64, 0.33), (0.21, 0.71), (0.15, 0.06))),
                       ("sRGB", ((0.64, 0.33), (0.30, 0.60), (0.15, 0.06)))):
        out[name] = (adapt @ m(prim, d65)).T          # rows: R, G, B
    return out


def test_the_list_is_the_srgb_set_and_a_whole_22_cube_in_prophoto():
    labs = gt.load_master_labs()
    r1 = gt.load_master_labs(gt.master_set_path())
    cube = gt.wide_cube_labs()
    assert len(r1) == 5960 and len(cube) == 22 ** 3 == 10648
    assert len(labs) == 16608
    assert labs[:5960] == r1 and labs[5960:] == cube
    # The cube's corners are black and the D50 white, its diagonal neutral.
    assert cube[0] == (0.0, 0.0, 0.0)
    assert cube[-1] == pytest.approx((100.0, 0.0, 0.0), abs=1e-9)


def test_the_cube_holds_srgb_and_adobe_rgb():
    """Every primary of sRGB and Adobe RGB (1998) is a mixture of ProPhoto
    RGB's, inside its cube: the list reaches further than both."""
    to_prophoto = np.linalg.inv(gt._prophoto_to_xyz_matrix())
    for name, xyz in _adobe_rgb_primaries_d50().items():
        lin = xyz @ to_prophoto.T
        assert np.all(lin >= -1e-6) and np.all(lin <= 1 + 1e-6), name


def test_the_list_is_the_same_every_time():
    assert gt.wide_cube_labs() == gt.wide_cube_labs()
    assert gt.MASTER_SET_VERSION == "PROVISIONAL-r2"


# --- k82: the spread, through Basti's ET-8550 profile -------------------------

@pytest.fixture(scope="module")
def et8550(tmp_path_factory):
    bin_dir = _bin_dir()
    prof = tmp_path_factory.mktemp("et8550") / ET8550.name
    shutil.copy(ET8550, prof)
    gt.clear_round_trip_cache()
    charts = {}
    for n in (100, 316, 1000):
        sel = gt.select_gamut_targets(prof, n, gt.MARGIN_SAFE,
                                      gt.INTENT_ABSOLUTE, bin_dir=bin_dir)
        printed = xr.forward_lab([d for _i, _l, d in sel.targets], prof,
                                 bin_dir, intent="a")
        printed += xr.forward_lab([d for d, _l in sel.corners], prof,
                                  bin_dir, intent="a")
        charts[n] = (sel, np.asarray(printed, float))
    density = gt._gamut_density(prof, bin_dir, "a", subprocess.run)
    yield {"charts": charts, "density": density, "profile": prof,
           "bin_dir": bin_dir}
    gt.clear_round_trip_cache()


def _nn(points):
    d = np.linalg.norm(points[:, None] - points[None], axis=2)
    np.fill_diagonal(d, np.inf)
    return d.min(axis=1)


def test_the_chart_has_exactly_the_count_asked_for(et8550):
    sel, printed = et8550["charts"][316]
    assert len(sel.targets) == 316 and len(sel.corners) == 8
    assert len(printed) == 324


def test_no_place_in_a_wide_gamut_is_left_empty(et8550):
    """THE k83 CATCH: 4.3.4's sRGB list left 35.7 dE76 between a colour this
    printer makes and the nearest patch of a 324-patch chart."""
    centres = et8550["density"][0]
    _sel, printed = et8550["charts"][316]
    _idx, gap = gt._nearest(centres, printed)
    assert gap.max() <= 17.0, f"an empty place {gap.max():.1f} dE76 wide"


def test_no_two_patches_crowd_together(et8550):
    """THE k82 CATCH: 4.3.4's closest pair was 2.9 dE76 apart in a chart
    whose patches are typically 11.6 apart.

    Judged for the colours spread over the volume. The grey steps follow the
    neutral axis at their own spacing (at least the eight the report's grey
    ramp needs, K31), so on a small chart they sit closer to each other than
    the volume's spacing, by design."""
    for n, (sel, printed) in et8550["charts"].items():
        d = np.linalg.norm(printed[:, None] - printed[None], axis=2)
        np.fill_diagonal(d, np.inf)
        nn = d.min(axis=1)
        spread = [i for i, (_k, lab, _d) in enumerate(sel.targets)
                  if math.hypot(lab[1], lab[2]) >= 1.0]
        assert nn[spread].min() >= 0.75 * np.median(nn[spread]), (
            f"{n}: closest pair {nn[spread].min():.2f}, "
            f"median {np.median(nn[spread]):.2f}")


def test_the_spacing_follows_the_patch_count(et8550):
    med = {}
    for n, (sel, p) in et8550["charts"].items():
        spread = [i for i, (_k, lab, _d) in enumerate(sel.targets)
                  if math.hypot(lab[1], lab[2]) >= 1.0]
        med[n] = float(np.median(_nn(p)[spread]))
    assert med[100] > med[316] > med[1000]
    # About the edge of the cube each patch owns: (volume / patches) ** 1/3.
    volume = float(et8550["density"][1].sum())
    for n, m in med.items():
        assert 0.8 <= m / (volume / (n + 8)) ** (1 / 3) <= 1.5, (n, m)


def test_grey_steps_are_every_reachable_step_up_to_the_budget(et8550):
    """4.3.10 (Basti, 2026-10-23, forum 149811): every grey step of the grey
    wedge the profile reaches, up to about one patch in eight, spaced evenly
    from the darkest to the lightest REACHABLE grey (not between the black
    and the white corner, as 4.3.5 to 4.3.9 did), each a distinct step for
    the report (at least GREY_LEVEL_TOL apart), and the report's own grey
    rule passes on every one of the three charts.

    MUTATION: put back 4.3.9's `_grey_steps` (as many as fit at the chart's
    spacing, between the corners): 8 steps on the 316 chart, not 38."""
    from workflow import measurement_report as MR
    for n, (sel, _printed) in et8550["charts"].items():
        levels = sorted(lab[0] for _k, lab, _d in sel.targets
                        if math.hypot(lab[1], lab[2]) < 1.0)
        budget = gt._neutral_budget(n)
        assert 8 <= len(levels) <= budget, (n, len(levels))
        assert min(np.diff(levels)) >= MR.GREY_LEVEL_TOL, (n, levels)
        assert MR.pick_even_grey_steps(levels)[0] is not None, (n, levels)
        if len(levels) == budget:
            # more reachable steps than the budget: spaced evenly, both
            # reachable ends included
            gaps = np.diff(levels)
            assert gaps.max() < 2.5 * gaps.mean(), (n, gaps)
    # the 316 chart holds every distinct grey this printer reaches, 38 of a
    # budget of 40, where 4.3.9 placed 8; the 100 chart its budget, 12
    sel, _p = et8550["charts"][316]
    assert sum(1 for _k, lab, _d in sel.targets
               if math.hypot(lab[1], lab[2]) < 1.0) == 38
    sel, _p = et8550["charts"][100]
    assert sum(1 for _k, lab, _d in sel.targets
               if math.hypot(lab[1], lab[2]) < 1.0) == gt._neutral_budget(100)


def test_the_count_line_and_the_chart_agree_on_what_is_reachable(et8550):
    sel, _p = et8550["charts"][316]
    reach, total = gt.gamut_coverage(et8550["profile"], gt.MARGIN_SAFE,
                                     gt.INTENT_ABSOLUTE,
                                     bin_dir=et8550["bin_dir"])
    assert (reach, total) == (sel.in_gamut_total, sel.master_total)
    assert total == 16608


def test_the_same_profile_and_count_give_the_same_chart(et8550):
    sel, _p = et8550["charts"][316]
    gt.clear_round_trip_cache()
    again = gt.select_gamut_targets(et8550["profile"], 316, gt.MARGIN_SAFE,
                                    gt.INTENT_ABSOLUTE,
                                    bin_dir=et8550["bin_dir"])
    assert [t[0] for t in again.targets] == [t[0] for t in sel.targets]
    assert [t[2] for t in again.targets] == [t[2] for t in sel.targets]


def test_only_colours_near_the_gamut_are_asked_about(et8550, monkeypatch):
    """The prefilter (_round_trip_near) changes no chart; it only spares
    xicclu the colours no grid cell of the gamut comes near."""
    asked = []
    real = gt._round_trip

    def spy(labs, *a, **k):
        asked.append(len(labs))
        return real(labs, *a, **k)
    monkeypatch.setattr(gt, "_round_trip", spy)
    gt.clear_round_trip_cache()
    near = gt.select_gamut_targets(et8550["profile"], 316, gt.MARGIN_SAFE,
                                   gt.INTENT_ABSOLUTE,
                                   bin_dir=et8550["bin_dir"])
    assert asked and asked[0] < 16608
    monkeypatch.setattr(gt, "_round_trip_near",
                        lambda labs, p, b, l, r, d: real(labs, p, b, l, r))
    gt.clear_round_trip_cache()
    every = gt.select_gamut_targets(et8550["profile"], 316, gt.MARGIN_SAFE,
                                    gt.INTENT_ABSOLUTE,
                                    bin_dir=et8550["bin_dir"])
    assert [t[0] for t in near.targets] == [t[0] for t in every.targets]
