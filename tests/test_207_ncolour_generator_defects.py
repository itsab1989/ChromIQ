"""#207: the patch set editor's CMYK / CMYK + extra inks generator defects.

Each test is one defect of the issue, written as the issue's own repro probe
(the numbers in the comments are what the code before #207 produced). R1, R2
and R6 are the design changes Basti approved on 2026-10-21 ("option 2"); the
composition details are pinned in test_separation_focused_nink_charts.py.
"""
from __future__ import annotations

import pytest

from workflow import patch_generators_nd as N


def _on(p, eps=0.05):
    return sum(1 for v in p if v > eps)


def _r3_program():
    return (N.per_ink_ramps(4, 60, 320) + N.ink_pair_overprints(4, 30, 320)
            + N.ink_triple_overprints(4, 20, 320)
            + N.rich_black_ramp(12, 4, 4, k_index=3, ink_limit=320))


def test_r3_unique_colours_never_switch_an_ink_on():
    prog = _r3_program()
    out = N.enforce_min_distance_nd(prog, 2.0, ink_limit=320)
    gained = sum(_on(b) > _on(a) for a, b in zip(prog, out))
    assert gained == 0                                    # was 121 of 548
    # a single-ink ramp step stays exactly what it was
    assert all(b == a for a, b in zip(prog, out) if _on(a, 0.0) == 1)


def test_r3_unique_colours_never_break_the_ink_limit():
    rb = N.rich_black_ramp(12, 4, 4, k_index=3, ink_limit=320)
    out = N.enforce_min_distance_nd(rb + N.neutral_ramp_device(33, 4, 320) + rb,
                                    2.0, ink_limit=320)
    assert max(sum(p) for p in out) <= 320.0 + 1e-9      # was 322.0


def test_r4_recentred_rings_stay_inside_the_limit():
    g = N.ring_grey_levels(9, 6, 2)
    c = {x: (min(100, (100 - x) * 1.2), min(100, (100 - x) * 1.1),
             min(100, (100 - x) * 1.1), 0.0) for x in g}
    rr = N.near_neutrals_device_recentred(9, 6, 2, 4, c, ink_limit=280)
    assert sum(sum(p) > 280 + 1e-9 for p in rr) == 0     # was 36, max 284.4


def test_r1_the_separation_fill_has_three_or_four_inks_per_patch():
    inks = ["c", "m", "y", "k", "o", "g", "v"]
    seed = N.per_ink_ramps(7, 8, 300)
    f = N.separation_fill_nd(seed, len(seed) + 400, inks, ink_limit=300)
    assert len(f) == 400
    # was 400 of 400 with all 7 inks; the design keeps about 8 % of 5+ ink
    # patches for the deep darks (research: 0 % starved the interior)
    assert sum(_on(p, 0.5) >= 5 for p in f) <= 0.10 * len(f)
    share34 = sum(_on(p, 0.5) in (3, 4) for p in f) / len(f)
    assert share34 >= 0.85
    assert max(sum(p) for p in f) <= 300.0 + 1e-6


def test_r2_pair_grids_sample_off_the_diagonal():
    out = N.ink_pair_grids(["c", "m", "y", "k"], 3, ink_limit=300)
    assert any(p[0] > 0 and p[1] > 0 and abs(p[0] - p[1]) > 40 for p in out)
    assert all(_on(p, 0.0) == 2 for p in out)


def test_r6_light_ramps_have_steps_under_five_percent():
    lv = N.ramp_levels(11, 100.0, "light")
    assert lv[0] < 5.0 and sum(v < 40.0 for v in lv) >= 5
    assert N.ramp_levels(11)[0] == pytest.approx(100 / 11)   # linear unchanged


@pytest.mark.parametrize("limit", [180.0, 240.0, 299.0])
def test_r7_grey_ramp_keeps_every_step_below_300_percent(limit):
    out = N.neutral_ramp_device(21, 4, ink_limit=limit)
    assert len(set(out)) == 21                            # was 13 at 180 %
    assert max(sum(p) for p in out) <= limit + 1e-9
    assert out[-1] == (0.0, 0.0, 0.0, 0.0)                # paper white kept
    assert all(p[0] == p[1] == p[2] and p[3] == 0.0 for p in out)


@pytest.mark.parametrize("limit", [300.0, 320.0, 400.0])
def test_r7_grey_ramp_is_unchanged_at_300_percent_and_more(limit):
    want = [N._invert_rgb_to_cmy(p, 4, limit) for p in N.neutral_ramp(21)]
    assert N.neutral_ramp_device(21, 4, ink_limit=limit) == want


def test_r8_deduplicate_keeps_inks_and_the_limit():
    ramp = N.per_ink_ramps(7, 33, 300)
    pts = ramp + ramp + [(0.0,) * 7] * 2
    out = N.deduplicate_nd(pts, ink_limit=300)
    assert len(out) == len(pts)
    assert all(_on(b, 0.0) == _on(a, 0.0) for a, b in zip(pts, out))
    assert all(sum(p) <= 300.0 + 1e-9 for p in out)
    full = [(100.0, 100.0, 100.0, 0.0)] * 4
    out = N.deduplicate_nd(full, ink_limit=300)
    assert all(sum(p) <= 300.0 + 1e-9 and _on(p, 0.0) == 3 for p in out)
    assert len(set(out)) == 4
