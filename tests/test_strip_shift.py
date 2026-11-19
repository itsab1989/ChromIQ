"""4.3.50: the strip SHIFT test (patch finder study, 2026-11-19), its numbers.

ArgyllCMS's strip patch finder is told only how many patches a strip has. The
white run-up before the first patch is a flat stretch too; when the strip's
label or a jolt at the start puts an edge in front of it, the finder can take
the run-up as patch 1, and every reading from there moves by one (all of them,
or only the first few when a later boundary is missed). A tester's i1Pro 2
strip came back like that with its first three patches moved, and the colour
check kept it (88.2 against its limit of 95).

The helper now refuses such a strip (``native/chartread_helper/chromiq_shift.c``,
called in ``chromiq_chartread.c`` after the colour check). These tests run its
Python twin, ``workflow/strip_shift.py``, which ``test_strip_shift_c.py`` holds
to the C file number for number, on:

* ``tests/data/strip_shift_regression.json``: anonymous strips derived from the
  measurements on the developer's disk (only numbers: the chart's paper XYZ,
  the read and the expected XYZ per patch; no names, no spectra). 400 strips
  that pass the colour check today, the 150 HARDEST of 4,671 by shift score
  among them, and the 7 real strips read one patch out that were found there;
* strips moved on purpose (start, end, the first k patches only, the whole
  strip), short (6) and long (30), on randomised colours and on ramps.

The thresholds and the margins they keep (measured on all 4,671 real strips,
~/Desktop/ChromIQ-work/2026-11-19_shift450/out):
  s_3 >= 10: the worst correct strip scores 2.2, the mildest real misread 11.4;
  s_2 >= 20 AND s_2 >= 0.5 x D_2: the worst correct strips score 17.8 (at
  0.26 x D_2) and 17.1 (at 0.38 x D_2), never both;
  one patch (k = 1): the end reading as read L* >= 85 and chroma <= 12 where
  the expected colour is >= 50 from the paper: the brightest such correct
  reading is L* 69.7.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from workflow import strip_shift as S

DATA = Path(__file__).parent / "data" / "strip_shift_regression.json"


@pytest.fixture(scope="module")
def strips():
    return json.loads(DATA.read_text(encoding="utf-8"))["strips"]


def _run(st):
    return S.shift_test(st["read"], st["exp"], st["paper"])


# --------------------------------------------------------------- the real cases

def test_the_kept_misread_of_2026_11_19_is_refused(strips):
    """Case 2 of the study: the run-up taken as patch 1, the real A3 dropped,
    A4 on in step. The colour check passed it (worst patch 88.2 < 95)."""
    case = strips[0]
    assert case["note"].startswith("case 2") and case["werror"] < 95
    r = _run(case)
    assert r.flagged and r.end == 0 and r.k == 3
    assert r.score == pytest.approx(49.0, abs=0.5)


def test_every_real_misread_the_colour_check_keeps_is_refused(strips):
    kept = [st for st in strips if st["label"] == "misread" and st["werror"] < 95]
    assert len(kept) == 2
    for st in kept:
        assert _run(st).flagged, st["note"]


def test_the_real_misreads_the_colour_check_already_stops_score_high_too(strips):
    """These never reach the shift test (the colour check's own window comes
    first, with Use Anyway); the score still sees four of five."""
    stopped = [st for st in strips if st["label"] == "misread" and st["werror"] >= 95]
    assert len(stopped) == 5
    assert sum(_run(st).flagged for st in stopped) >= 4


def test_no_correct_strip_is_refused(strips):
    honest = [st for st in strips if st["label"] == "honest"]
    assert len(honest) == 400
    flagged = [i for i, st in enumerate(honest) if _run(st).flagged]
    assert flagged == []


def test_the_margins_the_thresholds_keep_on_correct_strips(strips):
    """The hardest correct strips of the whole set are in the fixture."""
    s3 = s2 = r2 = -1e9
    for st in strips:
        if st["label"] != "honest":
            continue
        r = _run(st)
        for e in (0, 1):
            s3 = max(s3, r.s[e][1])
            s2 = max(s2, r.s[e][0])
            if r.d[e][0] > 0:
                r2 = max(r2, r.s[e][0] / r.d[e][0])
    assert s3 <= S.T3 - 7.0          # 2.2 measured: 7.8 below the limit
    assert s2 <= S.T2 - 2.0          # 17.8 measured
    assert r2 <= S.F2 - 0.1          # 0.38 measured


# ------------------------------------------------------- strips moved on purpose

PAPER_READ = (86.5, 89.7, 74.0)      # a paper as an instrument reads it


def _moved(read, k, end, paper=PAPER_READ):
    """What the finder delivers when it takes the white before the first
    patch (end 0) or after the last (end 1) as a patch: k patches moved, the
    k-th lost (k = len: the whole strip)."""
    r = list(read) if end == 0 else list(read)[::-1]
    k = min(k, len(r))
    out = [paper] + r[:k - 1] + r[k:]
    return out if end == 0 else out[::-1]


def _rate(strips, k, end):
    hit = tot = 0
    for st in strips:
        if st["label"] != "honest" or len(st["read"]) < 6:
            continue
        r = S.shift_test(_moved(st["read"], k, end), st["exp"], st["paper"])
        tot += 1
        hit += r.flagged
    return hit / tot


@pytest.mark.parametrize("end", [0, 1])
def test_a_whole_strip_moved_is_refused(strips, end):
    """92 % on all real strips; this fixture holds the 150 hardest, and a
    whole strip moved by one must also FIT moved by one (the FMAX guard)."""
    assert _rate(strips, 999, end) >= 0.78


@pytest.mark.parametrize("end", [0, 1])
def test_three_patches_moved_then_in_step_is_refused(strips, end):
    assert _rate(strips, 3, end) >= 0.90


@pytest.mark.parametrize("end", [0, 1])
def test_two_patches_moved_then_in_step_is_mostly_refused(strips, end):
    assert _rate(strips, 2, end) >= 0.70


@pytest.mark.parametrize("end", [0, 1])
def test_one_patch_moved_is_refused_by_the_papers_fingerprint(strips, end):
    """The commonest pattern of the study's simulation: the run-up taken as
    patch 1, the real patch 1 dropped, the rest in step. Caught where patch 1's
    colour is far from the paper (most of a chart); where it is near the paper
    a paper reading there is no evidence, and the test stays silent. 74 % on
    all real strips; this fixture holds the 150 hardest, so less."""
    assert _rate(strips, 1, end) >= 0.40


def test_the_papers_fingerprint_has_a_margin_on_correct_strips(strips):
    """Correct end readings that look like paper miss their own colour by
    28.9 at most on all 4,671 real strips (the limit is 50)."""
    worst = 0.0
    for st in strips:
        if st["label"] != "honest":
            continue
        yn = sum(e[1] for e in st["exp"]) / sum(r[1] for r in st["read"])
        for ix in (0, -1):
            lr = S._lab(st["read"][ix])
            if lr[0] >= S.P_L and math.hypot(lr[1], lr[2]) <= S.P_C:
                worst = max(worst, S._de(S._lab(st["read"][ix], yn), S._lab(st["exp"][ix])))
    assert worst <= S.P_D - 15.0


def test_a_chart_without_a_white_patch_does_not_make_a_light_grey_paper():
    """The suite's synthetic charts have no white: their brightest expected
    colour is a light cyan. A light neutral patch read correctly at the end of
    a strip is not the paper being read as a patch (found by
    test_pattern_variants_read_by_both_readers on helper 19e's first build)."""
    rng = np.random.default_rng(14)
    paper = _xyz((95.6, -58.9, -12.7))
    for _ in range(200):
        exp = _random_strip(18, rng)
        exp[-1] = _xyz((94.7, 0.2, -7.9))
        assert not S.shift_test(exp, exp, paper).flagged


# ------------------------------------------------ synthetic strips, short and long

_W = (96.42, 100.0, 82.49)


def _xyz(lab):
    L, a, b = lab
    fy = (L + 16) / 116
    f = (fy + a / 500, fy, fy - b / 200)
    return tuple(w * (t ** 3 if t > 6 / 29 else (t - 16 / 116) * 3 * (6 / 29) ** 2)
                 for w, t in zip(_W, f))


def _lab(x):
    return S._lab(x)


def _print(exp, rng, rough):
    """A correct reading. *rough*: the design is a rough device model (as in
    ChromIQ's .ti2), so the print misses it by tens of dE; otherwise the
    expected values are measured references (a few dE)."""
    out = []
    for e in exp:
        L, a, b = _lab(e)
        if rough:
            L = min(99.0, max(1.0, L * rng.uniform(0.85, 1.05) + rng.uniform(-6, 6)))
            a, b = a * rng.uniform(0.6, 1.0), b * rng.uniform(0.6, 1.0)
        out.append(_xyz((L + rng.normal(0, 1.5), a + rng.normal(0, 1.5), b + rng.normal(0, 1.5))))
    return out


PAPER_EXP = _xyz((100.0, 0.0, -2.0))


def _random_strip(n, rng):
    return [_xyz((rng.uniform(15, 92), rng.uniform(-60, 70), rng.uniform(-70, 80))) for _ in range(n)]


@pytest.mark.parametrize("n", [6, 18, 30])
@pytest.mark.parametrize("rough", [True, False])
def test_short_and_long_randomised_strips(n, rough):
    rng = np.random.default_rng(n * 7 + rough)
    false = caught = 0
    for _ in range(300):
        exp = _random_strip(n, rng)
        read = _print(exp, rng, rough)
        false += S.shift_test(read, exp, PAPER_EXP).flagged
        caught += S.shift_test(_moved(read, 3, int(rng.integers(2))), exp, PAPER_EXP).flagged
    assert false == 0
    assert caught >= 0.9 * 300


def _ramp(n, f, down=False):
    v = np.linspace(0, 1, n)
    if down:
        v = v[::-1]
    return [_xyz(f(t)) for t in v]


RAMPS = {
    "grey from white": lambda t: (100 - 95 * t, 0.0, -2.0),
    "grey from black": lambda t: (5 + 95 * t, 0.0, -2.0),
    "yellow from white": lambda t: (98 - 10 * t, -5 * t, 90 * t),
    "cyan from white": lambda t: (98 - 40 * t, -45 * t, -45 * t),
}


@pytest.mark.parametrize("name", list(RAMPS))
@pytest.mark.parametrize("n", [6, 12, 30])
def test_a_ramp_is_never_refused_when_read_correctly(name, n):
    rng = np.random.default_rng(n)
    exp = _ramp(n, RAMPS[name])
    for _ in range(200):
        assert not S.shift_test(_print(exp, rng, True), exp, PAPER_EXP).flagged


@pytest.mark.parametrize("n", [6, 12, 30])
def test_a_ramp_that_starts_on_white_stays_silent_even_when_moved(n):
    """Moved by one, a ramp starting on white looks like a correct reading of
    a slightly lighter print: the two cannot be told apart, and the test says
    nothing rather than guess."""
    rng = np.random.default_rng(3)
    exp = _ramp(n, RAMPS["grey from white"])
    for _ in range(100):
        assert not S.shift_test(_moved(_print(exp, rng, True), n, 0), exp, PAPER_EXP).flagged


def test_a_ramp_that_starts_dark_is_refused_when_moved():
    """A dark first patch read as paper is not a print difference."""
    rng = np.random.default_rng(4)
    exp = _ramp(12, RAMPS["grey from black"])
    hits = sum(S.shift_test(_moved(_print(exp, rng, True), 12, 0), exp, PAPER_EXP).flagged
               for _ in range(100))
    assert hits == 100


def test_too_short_or_unreadable_is_not_judged():
    exp = [_xyz((50, 40, 20))] * 3
    assert not S.shift_test(exp, exp, PAPER_EXP).flagged
    exp = _random_strip(8, np.random.default_rng(1))
    assert not S.shift_test([(0.0, 0.0, 0.0)] * 8, exp, PAPER_EXP).flagged
    assert not S.shift_test(exp, [(0.0, 0.0, 0.0)] * 8, PAPER_EXP).flagged


def test_the_twin_says_what_the_header_says():
    h = (Path(__file__).parents[1] / "native" / "chartread_helper" / "chromiq_shift.h").read_text(encoding="utf-8")
    for name, val in (("CQS_T3", S.T3), ("CQS_T2", S.T2), ("CQS_F2", S.F2),
                      ("CQS_QMIN", S.QMIN), ("CQS_NMIN", S.NMIN), ("CQS_P_L", S.P_L),
                      ("CQS_P_C", S.P_C), ("CQS_P_D", S.P_D), ("CQS_W", S.W),
                      ("CQS_T3_W", S.T3_W), ("CQS_FMAX", S.FMAX)):
        line = next(ln for ln in h.splitlines() if ln.startswith(f"#define {name} "))
        assert math.isclose(float(line.split()[2]), val), line


# ------------------------------------------------- a wrong strip is not a shift

def test_a_strip_read_in_place_of_another_is_never_called_moved():
    """With -S (ChromIQ's default) no wrong-strip question stands in front of
    the shift test. A strip of the same chart swiped in place of another fits
    its own row better than any shift (the guard on other rows): measured on
    the real strips, 0 of 4,931 such swipes flagged (1,916 without it)."""
    rng = np.random.default_rng(11)
    for n in (6, 18, 30):
        rows = [_random_strip(n, rng) for _ in range(12)]
        flagged = 0
        for _ in range(150):
            i, j = rng.choice(12, 2, replace=False)
            read = _print(rows[j], rng, True)            # strip j, filed as i
            other = S.other_rows_best(read, [r for k, r in enumerate(rows) if k != i])
            flagged += S.shift_test(read, rows[i], PAPER_EXP, other).flagged
        assert flagged == 0, n


def test_a_strip_from_another_chart_is_rarely_called_moved():
    """Nothing on this chart explains it, so only the fit guard (FMAX) stands:
    37 of 3,151 on the real strips (1.2 %), 1,202 without it."""
    rng = np.random.default_rng(12)
    flagged = 0
    for _ in range(600):
        rows = [_random_strip(18, rng) for _ in range(6)]
        read = _print(_random_strip(18, rng), rng, True)
        other = S.other_rows_best(read, rows[1:])
        flagged += S.shift_test(read, rows[0], PAPER_EXP, other).flagged
    assert flagged <= 0.03 * 600


def test_a_moved_strip_is_still_refused_with_the_other_rows_known():
    rng = np.random.default_rng(13)
    hits = 0
    for _ in range(300):
        rows = [_random_strip(18, rng) for _ in range(8)]
        read = _moved(_print(rows[0], rng, True), 3, 0)
        other = S.other_rows_best(read, rows[1:])
        hits += S.shift_test(read, rows[0], PAPER_EXP, other).flagged
    assert hits >= 0.9 * 300
