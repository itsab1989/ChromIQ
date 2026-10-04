"""Separation-focused chart sets for 5+ ink printers (agent 18, D-16).

Professional expanded-gamut charts (FOGRA55 / IDEAlliance ECG, X-Rite ECG
4200) sample ink SUBSETS: ramps with dense light tones, every two-ink
overprint as a grid, mostly three and four inks per patch, complementary
pairs less. These tests pin the new generators' composition, the ink limit,
determinism, and the fixes R3 (Ensure unique colours never breaks the ink
limit or switches an ink on), R4 (re-centred rings stay inside the limit) and
R5 (the dialog's ink order is Argyll's canonical order).
"""
from __future__ import annotations

import itertools

import pytest

from workflow import patch_generators_nd as ND

INKS7 = ["c", "m", "y", "k", "o", "g", "v"]


def _on(p):
    return sum(1 for v in p if v > 0.0)


# --- ramps -------------------------------------------------------------------

def test_light_ramp_puts_half_the_steps_below_40_percent():
    lv = ND.ramp_levels(11, 100.0, "light")
    assert lv[-1] == pytest.approx(100.0)
    assert sum(1 for v in lv if v < 40.0) >= 5
    assert lv == sorted(lv) and lv[0] > 0
    # the default spacing is unchanged
    assert ND.ramp_levels(4) == [25.0, 50.0, 75.0, 100.0]
    assert ND.per_ink_ramps(2, 4) == [(25.0, 0.0), (50.0, 0.0), (75.0, 0.0), (100.0, 0.0),
                                      (0.0, 25.0), (0.0, 50.0), (0.0, 75.0), (0.0, 100.0)]


def test_light_ramp_patches_are_single_ink_inside_the_limit():
    out = ND.per_ink_ramps(7, 12, ink_limit=80.0, spacing="light")
    assert len(out) == 84
    assert all(_on(p) == 1 and max(p) <= 80.0 + 1e-9 for p in out)


# --- pair grids ----------------------------------------------------------------

def test_pair_grids_are_grids_not_diagonals_and_keep_two_inks():
    out = ND.ink_pair_grids(INKS7, 3, ink_limit=320.0)
    assert len(out) == ND.ink_pair_grids_count(INKS7, 3)
    assert all(_on(p) == 2 for p in out)
    cm = sorted((round(p[0]), round(p[1])) for p in out if p[0] > 0 and p[1] > 0)
    assert (33, 100) in cm and (100, 33) in cm             # off the diagonal
    assert len(cm) == 9


def test_complementary_pairs_get_the_coarse_grid():
    out = ND.ink_pair_grids(INKS7, 3, ink_limit=320.0)
    co = [p for p in out if p[0] > 0 and p[4] > 0]          # C + O
    mg = [p for p in out if p[1] > 0 and p[5] > 0]          # M + G
    yv = [p for p in out if p[2] > 0 and p[6] > 0]          # Y + V
    mo = [p for p in out if p[1] > 0 and p[4] > 0]          # M + O (neighbours)
    assert len(co) == len(mg) == len(yv) == 4
    assert len(mo) == 9


def test_light_ink_pairs_with_its_parent_get_a_finer_grid():
    inks = ["c", "m", "y", "k", "lc", "lm"]
    out = ND.ink_pair_grids(inks, 3, ink_limit=300.0)
    c_lc = [p for p in out if p[0] > 0 and p[4] > 0]
    c_lm = [p for p in out if p[0] > 0 and p[5] > 0]
    assert len(c_lc) == 16 and len(c_lm) == 9


@pytest.mark.parametrize("limit", [120.0, 150.0, 200.0, 320.0])
def test_pair_grids_scale_into_the_limit_and_keep_the_ink_count(limit):
    out = ND.ink_pair_grids(INKS7, 4, ink_limit=limit)
    assert all(sum(p) <= limit + 1e-9 for p in out)
    assert all(_on(p) == 2 for p in out)


# --- separation fill ---------------------------------------------------------------

def test_separation_fill_uses_three_and_four_inks_only():
    seed = ND.per_ink_ramps(7, 8, 320.0)
    add = ND.separation_fill_nd(seed, len(seed) + 400, INKS7, ink_limit=320.0)
    assert len(add) == 400
    counts = {k: sum(1 for p in add if _on(p) == k) for k in range(8)}
    assert counts[3] + counts[4] == 400
    assert 120 < counts[3] < 280                              # share3 = 0.5
    assert all(sum(p) <= 320.0 + 1e-9 for p in add)
    assert all(min(v for v in p if v > 0) >= 8.0 * 320.0 / 400.0 - 1e-9 for p in add)


def test_separation_fill_prefers_cmyk_and_avoids_complementary_pairs():
    add = ND.separation_fill_nd([], 2000, INKS7, ink_limit=320.0, seed=3)
    act = [frozenset(i for i, v in enumerate(p) if v > 0) for p in add]
    cmyk = sum(1 for a in act if a <= {0, 1, 2, 3})
    comp = sum(1 for a in act if {0, 4} <= a or {1, 5} <= a or {2, 6} <= a)
    # of the 35 three-ink + 35 four-ink subsets only 4 + 1 lie inside CMYK,
    # so an unweighted draw would give about 7 %; the weights give more
    assert cmyk / len(add) > 0.10
    # complementary pairs: sampled (a full separation may use them) but rarer
    # than in an unweighted draw (about 50 % of 3-4 ink subsets hold one)
    assert 0 < comp / len(add) < 0.35


def test_separation_fill_is_deterministic_and_respects_existing():
    a = ND.separation_fill_nd([], 50, INKS7, ink_limit=300.0, seed=7)
    b = ND.separation_fill_nd([], 50, INKS7, ink_limit=300.0, seed=7)
    assert a == b
    assert ND.separation_fill_nd([(0.0,) * 7] * 60, 50, INKS7) == []


def test_separation_fill_on_cmyk_and_on_three_inks():
    add = ND.separation_fill_nd([], 100, ["c", "m", "y", "k"], ink_limit=300.0)
    assert all(_on(p) in (3, 4) for p in add)
    add3 = ND.separation_fill_nd([], 30, ["c", "m", "y"], ink_limit=250.0)
    assert all(_on(p) == 3 and sum(p) <= 250.0 + 1e-9 for p in add3)


def test_subset_weight():
    assert ND.subset_weight(["c", "m", "y", "k"]) == 1.0
    assert ND.subset_weight(["m", "y", "k", "o"]) == 1.0      # O replaces C
    assert ND.subset_weight(["c", "y", "o"]) == 0.25          # C with O
    assert ND.subset_weight(["k", "o", "g"]) == 0.5           # two extra inks
    assert ND.subset_weight(["c", "lc", "y"]) == 1.0          # light ink = parent


# --- fixes R3 / R4 -----------------------------------------------------------------

def test_min_distance_never_switches_an_ink_on_or_breaks_the_limit():
    import numpy as np
    lim = 320.0
    ramps = ND.per_ink_ramps(7, 17, lim)
    ramps2 = [tuple(v + (0.7 if v > 0 else 0) for v in p) for p in ramps]
    rng = np.random.default_rng(5)
    face = ND.project_ink_limit(rng.uniform(0, 100, (150, 7)), lim)
    near = ND.project_ink_limit(
        [tuple(v + rng.uniform(-0.8, 0.8) if v > 0 else v for v in p) for p in face], lim)
    prog = ramps + ND.ink_pair_grids(INKS7, 3, lim) + ramps2 + face + near
    out = ND.enforce_min_distance_nd(prog, 2.0, ink_limit=lim)
    assert len(out) == len(prog)
    assert all(sum(p) <= lim + 1e-6 for p in out)
    for a, b in zip(prog, out):
        assert {i for i, v in enumerate(b) if v > 0} <= {i for i, v in enumerate(a) if v > 0}


def test_min_distance_leaves_paper_white_repeats_alone():
    white = (0.0,) * 7
    assert ND.enforce_min_distance_nd([white, white], 2.0, ink_limit=300.0) == [white, white]


def test_recentred_rings_stay_inside_the_limit_when_the_neutral_carries_k():
    centers = {}
    for g in ND.ring_grey_levels(9, 10.0, 2):
        v = 100 - g
        centers[g] = (v, v * 0.95, v * 0.9, v * 0.6, 0.0, 0.0, 0.0)
    for lim in (300.0, 260.0):
        pts = ND.near_neutrals_device_recentred(9, 10.0, 2, 7, centers, ink_limit=lim)
        assert all(sum(p) <= lim + 1e-6 for p in pts)
        assert all(min(p) >= 0.0 for p in pts)


# --- the dialog (R5 and the new switches) -------------------------------------------

pytest.importorskip("PyQt6")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class _FakeSettings:
    def __init__(self):
        self.d = {}

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v):
        self.d[k] = v


@pytest.fixture
def dlg(qapp, tmp_path):
    from ui.dialogs.ti2_relayout_dialog import _NewChartDialog
    d = _NewChartDialog(tmp_path, _FakeSettings())
    yield d
    d.deleteLater()


def _seven_inks(dlg, order=("v", "o", "g")):
    dlg._device_type.setCurrentIndex(dlg._device_type.findData("cmykplus"))
    dlg._extra_inks = list(order)
    dlg._refresh_nch_state()


def test_ink_codes_follow_argylls_order_whatever_the_add_order(dlg):
    _seven_inks(dlg, ("v", "o", "g"))
    assert dlg._nch_ink_codes() == INKS7
    from workflow import ti2_relayout as R
    rep, fields = R.color_rep_for_inks(dlg._nch_ink_codes())
    assert rep == "CMYKOGV"


def test_new_switches_build_the_separation_focused_program(dlg):
    _seven_inks(dlg)
    dlg._ink_limit.setValue(320)
    dlg._nch_targen.setChecked(False)
    for name in ("neutral", "nearneutral", "whiteblack"):
        getattr(dlg, f"_gen_{name}").setChecked(False)
    dlg._nch_perink.setChecked(True)
    dlg._nch_perink_n.setValue(12)
    dlg._nch_perink_light.setChecked(True)
    dlg._nch_pairs.setChecked(True)
    dlg._nch_pairs_n.setValue(3)
    dlg._nch_pairs_grid.setChecked(True)
    dlg._gen_unique.setChecked(True)
    dlg._gen_fill.setChecked(True)
    dlg._gen_fill_sparse.setChecked(True)
    dlg._gen_fill_to.setValue(600)
    program = dlg._build_generated_program()
    assert len(program) == 600
    assert all(sum(p) <= 320.0 + 1e-6 for p in program)
    k = [_on(p) for p in program]
    assert sum(1 for x in k if x >= 5) == 0
    assert sum(1 for x in k if x in (3, 4)) >= 600 - 84 - ND.ink_pair_grids_count(INKS7, 3)
    # the count label agrees with what the row adds
    assert dlg._nch_pairs_patch_count() == ND.ink_pair_grids_count(INKS7, 3)


def test_new_switches_survive_the_state_round_trip(dlg, qapp, tmp_path):
    _seven_inks(dlg)
    dlg._nch_perink_light.setChecked(True)
    dlg._nch_pairs_grid.setChecked(True)
    dlg._gen_fill_sparse.setChecked(True)
    st = dlg._collect_gen_state()
    gen = st["device"]["gen"]
    assert gen["perink_light"] and gen["pairs_grid"] and gen["fill_sparse"]
    from ui.dialogs.ti2_relayout_dialog import _NewChartDialog
    d2 = _NewChartDialog(tmp_path, _FakeSettings())
    try:
        d2._apply_gen_state(st)
        assert d2._nch_perink_light.isChecked()
        assert d2._nch_pairs_grid.isChecked()
        assert d2._gen_fill_sparse.isChecked()
        # an older state without the keys loads with everything off
        old = dict(st, device=dict(st["device"], gen={k: v for k, v in gen.items()
                                                      if k not in ("perink_light", "pairs_grid",
                                                                   "fill_sparse")}))
        d2._apply_gen_state(old)
        assert not (d2._nch_perink_light.isChecked() or d2._nch_pairs_grid.isChecked()
                    or d2._gen_fill_sparse.isChecked())
    finally:
        d2.deleteLater()


def test_new_switches_are_hidden_for_rgb(dlg):
    dlg._device_type.setCurrentIndex(dlg._device_type.findData("rgb"))
    dlg._refresh_nch_state()
    for w in (dlg._nch_perink_light, dlg._nch_pairs_grid, dlg._gen_fill_sparse):
        assert w.isHidden()
