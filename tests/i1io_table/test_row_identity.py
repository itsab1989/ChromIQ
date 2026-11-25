"""THE ROW IDENTITY CHECK, judged on rows of a fixed, repository-safe palette (the new i1iO chart
layout, 25 Nov 2026): a row that lies right is never refused and never asked about, a row one or
two patches off is always refused where the check can judge it, another row is asked about, and a
row it cannot judge says why. Recorded rows of a real table are judged by a script outside the
repository, with this same code (a condition for shipping, not a gate test)."""
from __future__ import annotations

import random
from collections import Counter

import numpy as np
import pytest

from tests.i1io_table import bed_sim as B
from workflow.i1io import expected as ex
from workflow.i1io.table import identity as idn

N = 80


def _pairs(n=300, seed=3):
    """(expected Lab, measured Lab) of n colours: sRGB's idea of the device colours against the
    bed's printed spectra (another colour model)."""
    out = []
    for rgb in B.patch_set(n, seed):
        out.append((ex.lab(ex._srgb_xyz(rgb)), ex.lab(B.expected_xyz(rgb))))
    return out


PAIRS = _pairs()
WHITE = PAIRS[0]


def _row(rng, kind, k=0, n=24):
    if kind == "few":
        pool = [PAIRS[i] for i in rng.sample(range(len(PAIRS)), k)]
        row = [rng.choice(pool) for _ in range(n)]
    else:
        row = [PAIRS[i] for i in rng.sample(range(9, len(PAIRS)), n)]
        if kind == "pad":
            row[n - k:] = [WHITE] * k
    noisy = [(e, tuple(v + rng.gauss(0, 0.2) for v in m)) for e, m in row]
    return [e for e, _m in noisy], [m for _e, m in noisy]


def _judge(m, e, others=()):
    locs = [f"A{i + 1}" for i in range(len(e))]
    exp = dict(zip(locs, e))
    named = []
    for j, o in enumerate(others):
        ol = [f"O{j}-{i}" for i in range(len(o))]
        exp.update(zip(ol, o))
        named.append((f"row {j + 1}", ol))
    return idn.judge({loc: v for loc, v in zip(locs, m) if v is not None}, locs, exp, named)


def _verdict(v):
    return v["verdict"] if v["judged"] else "not judged"


def _shift(m, d):
    """The row read d patches on: what lies past its end is paper."""
    paper = WHITE[1]
    n = len(m)
    return [m[i + d] if 0 <= i + d < n else paper for i in range(n)]


def _count(kind, k=0, n=24, seed=1, change=None):
    rng = random.Random(seed)
    rows = [_row(rng, kind, k, n) for _ in range(N)]
    right, shifted, other = Counter(), Counter(), Counter()
    for i, (e, m) in enumerate(rows):
        mm = change(m, rng) if change else m
        right[_verdict(_judge(mm, e))] += 1
        for d in (1, -1, 2, -2):
            shifted[_verdict(_judge(_shift(mm, d), e))] += 1
        om = rows[(i + 1) % N][1]
        other[_verdict(_judge(change(om, rng) if change else om, e))] += 1
    return right, shifted, other


@pytest.mark.parametrize("n", (24, 16, 12))
def test_rows_of_many_colours(n):
    right, shifted, other = _count("rand", n=n)
    assert set(right) <= ({"ok"} if n > 12 else {"ok", "not judged"}) and right["ok"] > 0.7 * N
    # 12 patches moved by two leave ten pairs: the veto or at least the question
    judged = right["ok"]
    assert shifted["ok"] == 0
    assert shifted["shifted"] >= (4 * judged if n > 12 else 3.5 * judged)
    assert other["ok"] == 0 and other["ask"] >= 0.9 * judged


@pytest.mark.parametrize("k,judged_at_most", ((3, 0), (6, 0)))
def test_rows_of_few_colours_are_not_judged(k, judged_at_most):
    right, shifted, other = _count("few", k)
    for c in (right, shifted, other):
        assert sum(v for w, v in c.items() if w != "not judged") <= judged_at_most


def test_rows_of_12_colours_repeated():
    right, shifted, _other = _count("few", 12)
    judged = sum(v for w, v in right.items() if w != "not judged")
    assert judged >= 0.3 * N and right["shifted"] == 0 and right["ask"] == 0
    assert shifted["ok"] == 0


@pytest.mark.parametrize("pad,judged", ((6, True), (12, True), (14, False)))
def test_padding(pad, judged):
    right, shifted, other = _count("pad", pad)
    assert right["shifted"] == 0 and right["ask"] == 0
    assert (right["ok"] > 0.5 * N) if judged else set(right) == {"not judged"}
    if judged:
        assert shifted["ok"] == 0


def _bw(m, rng):
    return [(v[0], rng.gauss(0, 0.6), rng.gauss(0, 0.6)) for v in m]


def _matte(m, rng):
    return [(25 + 0.68 * v[0] + rng.gauss(0, 1.5), 0.35 * v[1] + rng.gauss(0, 1.5),
             0.35 * v[2] + rng.gauss(0, 1.5)) for v in m]


def _clogged(m, rng):
    return [(max(v[0], 45.0), v[1], v[2]) for v in m]


@pytest.mark.parametrize("change", (_bw, _matte, _clogged), ids=("bw", "matte", "clogged"))
def test_poor_prints_are_never_refused_and_never_asked_about(change):
    right, shifted, _other = _count("rand", change=change)
    assert set(right) == {"ok"}
    assert shifted["ok"] == 0


def test_the_neighbour_row_is_named():
    rng = random.Random(8)
    e1, _m1 = _row(rng, "rand")
    e2, m2 = _row(rng, "rand")
    v = _judge(m2, e1, others=[e2])
    assert v["verdict"] == "ask" and v["other"] == "row 1"
    assert "row 1" in idn.summary(v)


def test_a_row_read_in_part_is_judged_at_its_own_places():
    rng = random.Random(5)
    e, m = _row(rng, "rand")
    part = [v if 6 <= i < 20 else None for i, v in enumerate(m)]
    assert _judge(part, e)["verdict"] == "ok" and _judge(part, e)["patches"] == 14
    moved = [v if 6 <= i < 20 else None for i, v in enumerate(_shift(m, 1))]
    assert _judge(moved, e)["verdict"] == "shifted"
    few = [v if i < 11 else None for i, v in enumerate(m)]
    v = _judge(few, e)
    assert not v["judged"] and "11 patches, fewer than 12" in v["why"]
    # scattered: no pair of neighbours, so no shift can be seen, but the question stays
    other = _row(rng, "rand")[1]
    scattered = [v if i % 2 == 0 else None for i, v in enumerate(other)]
    v = _judge(scattered, e)
    assert v["judged"] and v["verdict"] == "ask"


def test_why_a_row_is_not_judged_is_said():
    rng = random.Random(6)
    e, m = _row(rng, "rand")
    flat = [(50.0 + 0.01 * i, 0.0, 0.0) for i in range(24)]
    for ee, words in ((flat, "lightness spreads by"), (e[:8], "fewer than 12"),
                      ([e[0]] * 13 + e[:11], "of its 24 patches are one colour"),
                      ([(10.0 + 4 * i, 0.0, 0.0) for i in range(24)], "resembles itself")):
        v = _judge(m[:len(ee)], ee)
        assert not v["judged"] and words in v["why"], (words, v["why"])
        assert idn.summary(v).startswith("row identity: not judged: ")
    assert idn.judge({}, [], {})["why"] == "the chart names no expected colours"


def test_it_never_raises():
    v = idn.judge({"A1": None}, ["A1"] * 30, {"A1": (1, 2, 3)})
    assert not v["judged"]
    v = idn.judge({f"A{i}": (float("nan"), 0, 0) for i in range(24)},
                  [f"A{i}" for i in range(24)], {f"A{i}": (i, 0, 0) for i in range(24)})
    assert not v["judged"]


def test_the_rank_correlation_is_spearmans():
    """Against numpy on ranks with ties."""
    rng = np.random.default_rng(4)
    for _ in range(50):
        a = rng.integers(0, 6, 15).astype(float)
        b = rng.normal(size=15)

        def rk(x):
            o = np.argsort(x, kind="stable")
            r = np.empty(len(x))
            r[o] = np.arange(len(x))
            for v in np.unique(x):
                r[x == v] = r[x == v].mean()
            return r
        want = np.corrcoef(rk(a), rk(b))[0, 1] if a.std() and b.std() else 0.0
        assert idn.spearman(list(a), list(b)) == pytest.approx(want, abs=1e-12)


# ---- the expected colours -----------------------------------------------------------------------

def test_the_charts_own_xyz_are_the_expected_colours(tmp_path):
    ch = B.build_chart(tmp_path, count=48)
    got, why = ex.expected_lab(ch.run.chart_ti2)
    assert why == "" and len(got) == 48
    truth = B.values_of(ch)
    for loc, lab in got.items():
        assert lab == pytest.approx(ex.lab(B.xyz_of(truth[loc])), abs=1.5)


def test_placeholder_xyz_fall_back_to_the_device_colours(tmp_path):
    ch = B.build_chart(tmp_path, count=48, xyz=lambda c: (50.0, 50.0, 50.0))
    got, why = ex.expected_lab(ch.run.chart_ti2)
    assert why == "" and len(got) == 48
    L = sorted(v[0] for v in got.values())
    assert L[0] < 5 and L[-1] > 95
    # ranks agree with what the printer would lay down
    truth = {loc: ex.lab(B.xyz_of(s))[0] for loc, s in B.values_of(ch).items()}
    locs = sorted(got)
    assert idn.spearman([got[k][0] for k in locs], [truth[k] for k in locs]) > 0.95


def test_no_expected_colours_says_why(tmp_path):
    ch = B.build_chart(tmp_path, count=48, colours=[(50.0, 50.0, 50.0)] * 48,
                       xyz=lambda c: (20.0, 20.0, 20.0))
    assert ex.expected_lab(ch.run.chart_ti2) == ({}, "the chart names no expected colours")
    assert ex.expected_lab(ch.run.chart_ti2, calibration=True) == ({}, "a calibration chart")
    assert ex.expected_lab(tmp_path / "none.ti2")[1] == "the chart cannot be read"


def _judge_L(levels, n=24):
    rng = random.Random(4)
    e = [(levels[i % len(levels)], rng.uniform(-60, 60), rng.uniform(-60, 60)) for i in range(n)]
    rng.shuffle(e)
    return _judge(e, e)


def test_the_lightness_must_spread_by_20():
    """Colourful rows of nearly one lightness (the rule looks at L* alone)."""
    for spread, judged in ((15.0, False), (19.0, False), (30.0, True)):
        v = _judge_L([50.0 + spread * k / 23.0 for k in range(24)])
        assert v["judged"] is judged, (spread, v["why"])
        if not judged:
            assert "lightness spreads by" in v["why"]


def test_lightnesses_are_different_from_2_units_on():
    """Eight lightnesses in four pairs 0.9 apart are four; spread over 2 units each, eight."""
    v = _judge_L([20.0, 20.9, 40.0, 40.9, 60.0, 60.9, 80.0, 80.9])
    assert not v["judged"] and v["why"].startswith("4 different expected lightnesses")
    assert _judge_L([20.0, 24.0, 40.0, 44.0, 60.0, 64.0, 80.0, 84.0])["judged"]


def test_placeholders_with_a_real_white_are_placeholders(tmp_path):
    """Every patch the same XYZ but the white's: the device colours are the expected ones."""
    ch = B.build_chart(tmp_path, count=48, xyz=lambda c: (
        (96.4, 100.0, 82.5) if tuple(c) == (100.0, 100.0, 100.0) else (50.0, 50.0, 50.0)))
    got, why = ex.expected_lab(ch.run.chart_ti2)
    assert why == "" and len({round(v[0], 1) for v in got.values()}) > 20
