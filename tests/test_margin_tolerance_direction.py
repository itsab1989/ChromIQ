"""The margin tolerance never keeps a reading whose ruler moved backwards
(independent review of 2026-11-16, BLOCKER-1), on the SAME C rule the helper
runs (tests/margin_lib.py) and the reader review's 28 real charts.

The case the review found: the instrument is set down on patch 2, the trigger
is pressed, it is pulled back to the edge of patch 1 (the aperture touches
patch 1 for 0 to 3 readings) and then swiped forward. ArgyllCMS refuses it.
The segments are patch 2 (backwards, a whole patch of travel), the sliver,
patch 2 (forwards), patches 3 to N, the white trailer. Measured by size alone
(the helper took fabs of the ruler's travel), rule L kept it and patch 1 got
patch 2's colour: 4,742 wrong keeps in 7,840 tries.

Since 2026-11-16b each segment's travel is SIGNED, the recording's largest
fall-back is measured over every ruler step, and a reading is looked at only
when nothing fell back more than 3 steps (chromiq_margin.c, rule 0a). Every
case below that moves backwards must be REFUSED (not merely "not wrong"),
because a reversal is never rescued. Each is decided three ways (see _both), so the
fall-back measure and the per-segment checks (direction, ground already
covered) are each proved on their own.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from tests import margin_lib as ml

DATA = Path(__file__).parent / "data"
pytestmark = pytest.mark.skipif(ml.lib() is None, reason="no C compiler here")
CHARTS = json.loads((DATA / "margin_charts.json").read_text(encoding="utf-8"))["charts"]


#: A row of the first chart whose end patches are not near paper white (its
#: row 0 has one, so rule 3 would refuse it before the rule under test).
E = 1


def _paper(lab):
    """The chart's paper white: its lightest expected patch (the white patch
    every one of these charts carries), as the instrument would see it."""
    flat = np.asarray(lab, float).reshape(-1, 3)
    return flat[np.argmax(flat[:, 0])] + np.array([0.3, 0.2, -0.3])


def _both(segs, steps, no, lab, exp):
    """Decide three ways: with the ruler as measured; with the fall-back
    forced to 0 (the per-segment checks alone); and with the travel's SIGN
    lost, as the helper of 41ba18fc7 handed it over (fabs), but the measured
    fall-back (that measure alone). Each must refuse."""
    _, _, back = ml.ruler_of(steps)
    labn = np.asarray(segs, float)
    return [ml.decide(labn, steps, no, lab, exp, 1),
            ml.decide(labn, steps, no, lab, exp, 1, back=0.0),
            ml.decide(labn, np.abs(steps), no, lab, exp, 1, back=back)]


def _sweep(build, seed=7, preds=(0, 3, 6, 10)):
    """build(prn, N, exp, rng, paper) -> list of (segs, steps, no); every one moves
    backwards somewhere. Returns (tries, accepted)."""
    rng = np.random.default_rng(seed)
    tries = acc = 0
    examples = []
    for name, rows in CHARTS.items():
        lab = np.array(rows, float)
        for pred in preds:
            prn = lab + rng.normal(0, pred / np.sqrt(3), lab.shape)
            for exp in range(lab.shape[0]):
                for segs, steps, no in build(prn, lab.shape[1], exp, rng, _paper(lab)):
                    segs = np.asarray(segs) + rng.normal(0, 0.3 / np.sqrt(3), (len(segs), 3))
                    for r in _both(segs, steps, no, lab, exp):
                        tries += 1
                        if r["accept"]:
                            acc += 1
                            if len(examples) < 3:
                                examples.append((name, exp, r["rule"], r["sel"][:4]))
    return tries, acc, examples


def _fw(rng, k):
    return list(rng.uniform(0.9, 1.1, k) * 40)


def test_the_reviewers_nudge_back_is_never_kept():
    """review/nudge.py, ported: set down on patch 2, pulled back to the edge
    of patch 1 (a sliver of 0 to 3 readings), then swiped; no white leader."""
    def build(prn, N, exp, rng, PAPER):
        out = []
        for sl_no in (0, 1, 2, 3):
            if sl_no:
                segs = [prn[exp, 1], prn[exp, 0], prn[exp, 1], *prn[exp, 2:], PAPER]
                steps = [-rng.uniform(0.9, 1.1) * 40, rng.uniform(-3, 3), *_fw(rng, N - 1), 40]
                no = [14, sl_no, *([14] * (N - 1)), 30]
            else:
                segs = [prn[exp, 1], prn[exp, 1], *prn[exp, 2:], PAPER]
                steps = [-rng.uniform(0.9, 1.1) * 40, *_fw(rng, N - 1), 40]
                no = [14, *([14] * (N - 1)), 30]
            out.append((segs, steps, no))
        return out
    tries, acc, ex = _sweep(build)
    assert tries == 3 * 7840          # the review's 7,840, each decided three ways
    assert acc == 0, ex


def test_a_wiggle_over_one_patch_after_a_late_start_is_never_kept():
    """review/adv.py wiggle_late2: started two patches in, then over patch m
    forwards, a sliver of m+1, back over m, a sliver of m-1, forwards over m."""
    def build(prn, N, exp, rng, PAPER):
        out = []
        for m in range(2, N - 1, 3):
            pre = list(prn[exp, 2:m])
            segs = [*pre, prn[exp, m], prn[exp, m + 1], prn[exp, m], prn[exp, m - 1],
                    prn[exp, m], *prn[exp, m + 1:], PAPER]
            steps = [*_fw(rng, len(pre)), 40, rng.uniform(0, 8), -40, -rng.uniform(0, 8),
                     40, *_fw(rng, N - m - 1), 40]
            no = [*([14] * len(pre)), 14, int(rng.integers(1, 4)), 14,
                  int(rng.integers(1, 4)), 14, *([14] * (N - m - 1)), 30]
            out.append((segs, steps, no))
            out.append((segs + [PAPER], steps + [40], no + [30]))
        return out
    tries, acc, ex = _sweep(build, seed=11, preds=(0, 6))
    assert tries > 2000
    assert acc == 0, ex


def test_a_nudge_forward_then_back_is_never_kept():
    """Set down on patch 1 or 2, nudged forwards over it into the next one,
    pulled back to where it started (or to the patch before), then swiped."""
    def build(prn, N, exp, rng, PAPER):
        out = []
        for s0 in (0, 1):
            nudge = rng.uniform(0.9, 1.1) * 40
            segs = [prn[exp, s0], prn[exp, s0 + 1], prn[exp, s0],
                    *prn[exp, s0:], PAPER]
            steps = [nudge, rng.uniform(0, 3), -nudge, *_fw(rng, N - s0), 40]
            no = [14, int(rng.integers(1, 4)), 14, *([14] * (N - s0)), 30]
            out.append((segs, steps, no))
            # with a white leader before it (rule M's shape)
            out.append(([PAPER, *segs], [40, *steps], [30, *no]))
        return out
    tries, acc, ex = _sweep(build, seed=13, preds=(0, 6))
    assert acc == 0, ex
    assert tries > 1000


@pytest.mark.parametrize("drift,where", [(5, "inside"), (8, "inside"),
                                         (5, "after"), (12, "after")])
def test_a_pause_that_drifts_back_more_than_the_ruler_allows_is_refused(drift, where):
    def build(prn, N, exp, rng, PAPER):
        h = N // 2
        if where == "inside":
            segs = [PAPER, *prn[exp, :h], prn[exp, h - 1], *prn[exp, h:], PAPER]
            steps = [40, *_fw(rng, h), -float(drift), *_fw(rng, N - h), 40]
            no = [30, *([14] * h), 40, *([14] * (N - h)), 30]
        else:
            segs = [PAPER, *prn[exp], prn[exp, -1], PAPER]
            steps = [40, *_fw(rng, N), -float(drift), 40]
            no = [30, *([14] * N), 40, 30]
        return [(segs, steps, no)]
    tries, acc, ex = _sweep(build, seed=17, preds=(0,))
    assert acc == 0, ex


def test_a_pause_that_drifts_back_within_the_ruler_tolerance_keeps_nothing_wrong():
    """A drift of 1 to 3 steps is what a resting reader shows: allowed, but
    whatever is kept must still be the expected row in order."""
    rng = np.random.default_rng(19)
    kept = wrong = 0
    for name, rows in CHARTS.items():
        lab = np.array(rows, float)
        N = lab.shape[1]
        PAPER = _paper(lab)
        for exp in range(lab.shape[0]):
            U = lab[exp]
            for drift in (1.0, 2.0, 3.0):
                segs = np.array([PAPER, *U, U[-1], PAPER])
                steps = [40, *_fw(rng, N), -drift, 40]
                no = [30, *([14] * N), 40, 30]
                r = ml.decide(segs, steps, no, lab, exp, 2)
                if r["accept"]:
                    kept += 1
                    if r["sel"] != list(range(1, N + 1)):
                        wrong += 1
    assert wrong == 0
    assert kept > 100      # the tolerance does let a resting reader through


def test_a_reversal_at_the_end_of_the_row_is_refused():
    def build(prn, N, exp, rng, PAPER):
        out = []
        # over the last patch, back over it, forwards over it again
        segs = [PAPER, *prn[exp], prn[exp, -1], prn[exp, -1], PAPER]
        steps = [40, *_fw(rng, N), -40, 40, 40]
        out.append((segs, steps, [30, *([14] * N), 14, 14, 30]))
        # into the trailer, back over the last patch, stopped there
        segs = [PAPER, *prn[exp], PAPER, prn[exp, -1]]
        steps = [40, *_fw(rng, N), 30, -40]
        out.append((segs, steps, [30, *([14] * N), 20, 14]))
        # one short, back over the patch before the last, into the trailer
        segs = [PAPER, *prn[exp, :-1], prn[exp, -2], prn[exp, -1], PAPER]
        steps = [40, *_fw(rng, N - 1), -40, 40, 40]
        out.append((segs, steps, [30, *([14] * (N - 1)), 14, 14, 30]))
        return out
    tries, acc, ex = _sweep(build, seed=23, preds=(0, 6))
    assert acc == 0, ex


def test_a_segment_on_ground_already_covered_is_refused_even_moving_forwards():
    """Defence in depth: positions handed over that revisit ground (a second
    pass recorded as two forward segments) refuse, whatever the fall-back."""
    lab = np.array(next(iter(CHARTS.values())), float)
    PAPER = _paper(lab)
    N = lab.shape[1]
    U = lab[E]
    segs = np.array([PAPER, *U, PAPER])
    steps = [40.0] * (N + 2)
    p0 = list(np.arange(N + 2) * 40.0)
    assert ml.decide(segs, steps, [30, *([14] * N), 30], lab, E, 2, p0=p0)["accept"]
    p0[5] = p0[4]                     # segment 6 starts where segment 5 started
    r = ml.decide(segs, steps, [30, *([14] * N), 30], lab, E, 2, p0=p0, back=0.0)
    assert not r["accept"] and "already read" in r["why"]


def test_an_unknown_fall_back_refuses():
    lab = np.array(next(iter(CHARTS.values())), float)
    PAPER = _paper(lab)
    N = lab.shape[1]
    segs = np.array([PAPER, *lab[E], PAPER])
    r = ml.decide(segs, [40.0] * (N + 2), [30, *([14] * N), 30], lab, E, 2, back=-1.0)
    assert not r["accept"] and "not known" in r["why"]


def test_a_strip_swiped_the_other_way_is_measured_against_its_own_direction():
    """Negative travel throughout is a strip swiped the other way round, not a
    reversal: it is judged exactly as the same strip swiped forwards."""
    lab = np.array(next(iter(CHARTS.values())), float)
    PAPER = _paper(lab)
    N = lab.shape[1]
    segs = np.array([PAPER, PAPER, *lab[E], PAPER])
    no = [30, 30, *([14] * N), 30]
    fw = ml.decide(segs, [40.0] * (N + 3), no, lab, E, 2)
    bw = ml.decide(segs, [-40.0] * (N + 3), no, lab, E, 2)
    assert fw["accept"] and bw["accept"] and fw["sel"] == bw["sel"]


def test_the_two_real_pulls_back_stay_refused_by_the_direction_rule():
    """Strip AL of the tester's third session (2026-11-15): two recordings in
    which the ruler fell back 40 and 46 steps. ArgyllCMS refused both."""
    fix = json.loads((DATA / "margin_fixtures.json").read_text(encoding="utf-8"))
    sess = next(s for s in fix["sessions"] if s["session"] == "20261115-173446")
    al = [s for s in sess["strips"] if s["strip"] == "AL" and s["verdict"] == "refused"]
    assert sorted(s["ruler_back"] for s in al) == [40.0, 46.0]
    lab = np.array(next(iter(CHARTS.values())), float)
    PAPER = _paper(lab)
    for s in al:
        c = s["candidates"]
        r = ml.decide(ml.band_lab(np.array([x[3:6] for x in c])), [x[2] for x in c],
                      [x[1] for x in c], lab, E, 1, p0=[x[6] for x in c],
                      net=float(s["ruler_sign"]), back=s["ruler_back"])
        assert not r["accept"] and "moved back" in r["why"]


def test_every_correct_recording_of_the_tester_is_within_the_tolerance():
    """The tolerance's own evidence: apart from the two pulls back, no strip
    of the three sessions fell back more than 2 steps."""
    fix = json.loads((DATA / "margin_fixtures.json").read_text(encoding="utf-8"))
    backs = [s["ruler_back"] for ss in fix["sessions"] for s in ss["strips"]]
    assert len(backs) == 159
    assert sorted(b for b in backs if b > 3) == [40.0, 46.0]
    assert max(b for b in backs if b <= 3) == 2.0


@pytest.mark.parametrize("N,ok", [(7, False), (8, True)])
def test_rows_of_fewer_than_8_patches_are_not_looked_at(N, ok):
    lab = np.array(next(iter(CHARTS.values())), float)[:, :N]
    PAPER = _paper(np.array(next(iter(CHARTS.values())), float))
    segs = np.array([PAPER, PAPER, *lab[E], PAPER])
    r = ml.decide(segs, [40.0] * (N + 3), [30, 30, *([14] * N), 30], lab, E, 2)
    assert r["accept"] is ok


@pytest.mark.parametrize("off", [4.0, 5.0, 6.0])
def test_rule_l_refuses_a_trailer_that_is_a_board_not_paper(off):
    """No leader; after the last patch the paper margin, then a jig or board
    4 to 6 dE from it, darker. The trailer is not paper white: rule L refuses
    (and so does rule M, which has no white leader to go by)."""
    lab = np.array(next(iter(CHARTS.values())), float)
    PAPER = _paper(lab)
    N = lab.shape[1]
    # mostly in b* (a grey or bluish board), its L* within the 2 L* of the old test
    board = PAPER + off * np.array([-0.2, 0.3, -0.932]) / np.linalg.norm([-0.2, 0.3, -0.932])
    segs = np.array([*lab[E], PAPER, board])
    r = ml.decide(segs, [40.0] * (N + 2), [*([14] * N), 20, 30], lab, E, 1)
    assert not r["accept"]
    assert r["why_l"] in ("the trailer is not paper white",
                          "what would be left out is not paper white")
    # a narrow paper margin (a sliver the ruler leaves out) before the board:
    # 41ba18fc7 took the board as the paper and kept the strip
    segs = np.array([*lab[E], PAPER, board])
    r = ml.decide(segs, [40.0] * N + [4.0, 40.0], [*([14] * N), 3, 30], lab, E, 1)
    assert not r["accept"] and r["why_l"] == "the trailer is not paper white"
    # the same strip ending on paper is kept
    segs = np.array([*lab[E], PAPER])
    assert ml.decide(segs, [40.0] * (N + 1), [*([14] * N), 30], lab, E, 1)["accept"]
