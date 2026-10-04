"""The research benchmark's decision statistics, protocol v2.1 (agent 6b,
2026-10-03).

v2's ``stats.py`` formed p from the bootstrap percentiles, so p could not
fall below 1 / 2000 = 0.0005, while Holm over a full baseline (~384 rows)
needs 0.05 / 384 = 0.00013 for its first rejection: every row read TIE, an
82 % improvement included. v2.1 takes p from the bootstrap standard error
(Student t), resamples the dense neutral ramps in blocks, keeps Holm over the
whole comparison and reads the placeholder seed term as the protocol states
it. Each test below pins one of those, and the null calibration that makes
the p-values honest.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from benchmarks.research import stats as S


def _ar1(rng, n, phi=0.95, sd=0.3):
    e = np.empty(n)
    e[0] = rng.normal() * sd
    s = sd * math.sqrt(1 - phi * phi)
    for i in range(1, n):
        e[i] = phi * e[i - 1] + rng.normal() * s
    return e


def test_the_p_value_has_no_floor_above_a_full_baselines_holm_threshold():
    a = np.random.default_rng(2).gamma(2.0, 0.2, 2000)
    r = S.paired_bootstrap(a, a * 0.8, "median", n_boot=2000)
    assert r["p_percentile"] == pytest.approx(1 / 2000)      # v2's floor, kept as a column
    assert r["p"] < 0.05 / 1000                              # v2.1 resolves a 1000-row family
    assert r["ci95"][1] < 0


def test_an_82_percent_improvement_is_better_in_a_384_row_family():
    """Agent 5's X5 neutral -82 % read TIE under v2 because of the floor."""
    rng = np.random.default_rng(5)
    rows = []
    for i in range(384):
        a = rng.gamma(2.0, 0.2, 400)
        b = a * (0.18 if i == 0 else 1.0) + (0 if i == 0 else rng.normal(0, 0.01, 400))
        r = S.paired_bootstrap(a, b, "median", n_boot=300, seed=i)
        r.update(dataset=f"D{i}", variant="typical", reader="argyll",
                 endpoint="a2b.median")
        rows.append(r)
    S.decide(rows)
    assert rows[0]["verdict"] == "BETTER"
    assert sum(r["verdict"] != "TIE" for r in rows) == 1


def test_the_student_t_tail_is_right():
    assert S.t_two_sided_p(2.228, 10) == pytest.approx(0.05, abs=2e-4)
    assert S.t_two_sided_p(12.706, 1) == pytest.approx(0.05, abs=2e-4)
    assert S.t_two_sided_p(1.96, 1e7) == pytest.approx(0.05, abs=2e-4)
    assert S.t_two_sided_p(3.84, 1e7) == pytest.approx(math.erfc(3.84 / math.sqrt(2)), rel=1e-3)
    assert S.t_two_sided_p(0.0, 5) == pytest.approx(1.0)


def test_holm_steps_down_in_p_order_and_stops_at_the_first_failure():
    # sorted: 0.005 <= 0.05/4, 0.01 <= 0.05/3, 0.03 > 0.05/2 -> stop
    assert S.holm([0.01, 0.04, 0.03, 0.005]) == [True, False, False, True]
    # 0.04 would pass 0.05/1 on its own, but the step-down already stopped
    assert S.holm([0.04, 0.03, 0.001]) == [False, False, True]
    assert S.holm([0.03, 0.02, 0.001]) == [True, True, True]
    # ties: order-independent
    assert S.holm([0.0125] * 4) == [True] * 4
    assert S.holm([]) == []


def test_a_row_is_significant_only_if_its_95_ci_excludes_zero():
    rows = [{"p": 1e-9, "ci95": [-0.1, 0.05], "diff": -0.5, "a": 1.0,
             "dataset": "X3", "variant": "typical", "reader": "argyll",
             "endpoint": "a2b.median"}]
    S.decide(rows)
    assert rows[0]["verdict"] == "TIE" and not rows[0]["holm_significant"]


def test_the_placeholder_seed_term_is_the_protocols_term_not_twice_it():
    rows = []
    for ep in ("a2b.median", "a2b.p95", "neutral_hi.mean"):
        rows.append({"p": 1.0, "ci95": [-1, 1], "diff": 0.0, "a": 0.1,
                     "dataset": "X3", "variant": "typical", "reader": "argyll",
                     "endpoint": ep})
    S.decide(rows)
    assert [r["min_effect"] for r in rows] == pytest.approx([0.03, 0.10, 0.03])
    assert all(r["seed_sd_source"] == "placeholder" for r in rows)


def test_independent_points_get_block_one_and_a_dense_ramp_a_long_block():
    rng = np.random.default_rng(3)
    assert S.block_length(rng.normal(size=2000)) == 1
    assert S.block_length(_ar1(rng, 360)) >= 8


def test_the_bootstrap_is_seeded():
    a = np.random.default_rng(4).gamma(2.0, 0.2, 500)
    b = a + np.random.default_rng(5).normal(0, 0.05, 500)
    assert S.paired_bootstrap(a, b, "p95", n_boot=200) == S.paired_bootstrap(a, b, "p95", n_boot=200)


def test_null_cloud_rows_hold_their_level_and_no_resampling_of_a_ramp_does():
    """Identical engines plus noise. Point clouds: exchangeable skewed pairs;
    v2.1's rate at nominal 0.05 must be about 0.05. Ramps: one curve plus two
    independent smooth (AR(1), phi 0.95) noise curves; resampling the ramp's
    points, iid (v2) or in blocks, rejects far too often. That is why v2.1
    takes ramp rows out of the point-resampling family."""
    rng = np.random.default_rng(6)
    base = np.linspace(3.0, 0.5, 240)
    rates = {"cloud": [], "ramp_block": [], "ramp_iid": []}
    for i in range(150):
        u, v = rng.gamma(1.5, 0.3, 300), rng.gamma(1.5, 0.3, 300)
        sw = rng.random(300) < 0.5
        a, b = np.where(sw, u, v), np.where(sw, v, u)
        rates["cloud"].append(S.paired_bootstrap(a, b, "median", n_boot=400, seed=i)["p"])
        ra, rb = np.abs(base + _ar1(rng, 240)), np.abs(base + _ar1(rng, 240))
        rates["ramp_block"].append(S.paired_bootstrap(ra, rb, "mean", n_boot=200, seed=i,
                                                      block="auto")["p"])
        rates["ramp_iid"].append(S.paired_bootstrap(ra, rb, "mean", n_boot=200, seed=i)["p"])
    rej = {k: float(np.mean(np.array(v) <= 0.05)) for k, v in rates.items()}
    assert rej["cloud"] <= 0.09
    assert rej["ramp_block"] >= 0.15
    assert rej["ramp_iid"] >= 0.4


def test_ramp_rows_are_starred_single_build_verdicts_outside_the_holm_family():
    rows = [{"p": 1e-12, "ci95": [-0.6, -0.4], "diff": -0.5, "a": 1.0, "dataset": "X3",
             "variant": "typical", "reader": "argyll", "endpoint": "neutral_hi.mean"},
            {"p": 1e-12, "ci95": [0.001, 0.002], "diff": 0.0015, "a": 1.0, "dataset": "X3",
             "variant": "typical", "reader": "argyll", "endpoint": "neutral_de.median"},
            {"p": 0.04, "ci95": [-0.6, -0.4], "diff": -0.5, "a": 1.0, "dataset": "X3",
             "variant": "typical", "reader": "argyll", "endpoint": "a2b.median"}]
    S.decide(rows)
    assert [r["verdict"] for r in rows] == ["BETTER*", "TIE", "BETTER"]
    assert rows[2]["family_size"] == 1          # 0.04 <= 0.05 / 1: ramps not counted
    assert not rows[0]["holm_significant"]


def test_ramp_rows_are_confirmed_only_across_enough_seeds():
    assert S.sign_flip_p([-0.5] * 5) == pytest.approx(2 / 32)    # 5 seeds cannot reach 0.05
    assert S.sign_flip_p([-0.5] * 10) == pytest.approx(2 / 1024)
    assert S.sign_flip_p([0.0] * 6) == 1.0
    assert S.sign_flip_p([-1, 1, -1, 1, -1, 1]) == 1.0

    def seeds(k, d):
        return [{"diff": d, "a": 1.0, "min_effect": 0.03, "dataset": "X3",
                 "variant": f"seed{i}", "reader": "argyll", "endpoint": "neutral_hi.mean"}
                for i in range(k)]
    assert S.ramp_seed_verdicts(seeds(5, -0.5))[0]["verdict"] == "TIE"
    assert S.ramp_seed_verdicts(seeds(10, -0.5))[0]["verdict"] == "BETTER"
    assert S.ramp_seed_verdicts(seeds(10, 0.01))[0]["verdict"] == "TIE"   # below min effect


def test_family_wise_error_of_a_null_family_is_at_most_alpha():
    rng = np.random.default_rng(7)
    any_rej = 0
    for rep in range(30):
        rows = []
        for i in range(30):
            u, v = rng.gamma(1.5, 0.3, 200), rng.gamma(1.5, 0.3, 200)
            sw = rng.random(200) < 0.5
            r = S.paired_bootstrap(np.where(sw, u, v), np.where(sw, v, u),
                                   "median", n_boot=600, seed=rep * 100 + i)
            r.update(dataset=f"D{i // 6}", variant="typical", reader="argyll",
                     endpoint=f"a2b.e{i % 6}", a=1.0, min_effect=0.0)
            rows.append(r)
        S.decide(rows, keep_min_effect=True)
        any_rej += any(r["holm_significant"] for r in rows)
    assert any_rej / 30 <= 0.10


def test_identical_engines_tie_with_p_one():
    a = np.random.default_rng(1).gamma(2.0, 0.2, 3000)
    r = S.paired_bootstrap(a, a.copy(), "median", n_boot=200)
    assert r["diff"] == 0.0 and r["p"] == 1.0 and r["ci95"] == [0.0, 0.0]


def _row(ds, var, rd, ep, diff, p=1e-12, a=1.0):
    return {"p": p, "ci95": sorted([diff * 0.9, diff * 1.1]) if diff else [-1, 1],
            "diff": diff, "a": a, "dataset": ds, "variant": var, "reader": rd,
            "endpoint": ep}


def test_the_no_regression_test_reads_the_per_printer_x_endpoint_column():
    """D-03 / D-09: a loss that the whole-comparison Holm would hide (p 0.02
    among 304 rows) still fails the no-regression test, because a larger
    family must not shield a candidate."""
    rows = [_row(f"D{i}", "typical", "argyll", "a2b.median", -0.001, p=0.5) for i in range(300)]
    rows += [_row("X3", v, rd, "a2b.p95", +0.5, p=0.003)
             for v in ("typical", "pessimistic") for rd in ("argyll", "lcms")]
    S.decide(rows)
    loss = rows[-1]
    assert loss["verdict"] == "TIE" and loss["verdict_per_printer_endpoint"] == "WORSE"
    nr = S.no_regression({"rows": rows, "ramp_seeds": []})
    assert not nr["pass"] and len(nr["worse"]) == 4


def test_a_single_build_ramp_loss_stays_open_until_seeds_clear_it():
    rows = [_row("X3", "typical", "argyll", "neutral_hi.mean", +0.5)]
    S.decide(rows)
    assert rows[0]["verdict"] == "WORSE*"
    nr = S.no_regression({"rows": rows, "ramp_seeds": []})
    assert not nr["pass"] and nr["open_ramp_rows"]
    seeds = [{"dataset": "X3", "reader": "argyll", "endpoint": "neutral_hi.mean",
              "verdict": "TIE"}]
    assert S.no_regression({"rows": rows}, seeds)["pass"]
    seeds[0]["verdict"] = "WORSE"
    assert not S.no_regression({"rows": rows}, seeds)["pass"]


def test_no_regression_passes_when_nothing_is_worse():
    rows = [_row("X3", "typical", "argyll", "a2b.median", -0.5),
            _row("X3", "typical", "argyll", "neutral_de.median", +0.001)]
    S.decide(rows)
    assert S.no_regression({"rows": rows, "ramp_seeds": []})["pass"]
