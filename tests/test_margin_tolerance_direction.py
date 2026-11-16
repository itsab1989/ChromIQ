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


def _printed(lab, rng, pred):
    """A 'printed' chart, as the review's adv.py: the expected colours with a
    systematic and a per-patch error."""
    P = lab.copy()
    P[..., 0] = 50 + (P[..., 0] - 50) * rng.uniform(0.85, 1.05) + rng.uniform(-3, 3)
    P[..., 1:] *= rng.uniform(0.75, 1.05)
    return P + rng.normal(0, pred / np.sqrt(3), P.shape)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_a_late_start_before_a_board_and_a_jump_into_the_neighbour_row_are_never_kept(seed):
    """Found by re-running the review's adv.py hunt in fix round 1 (seed 1,
    3 trials): 5 of 4,404 "board_lateM1" (white leader, started one patch in,
    paper, paper, then a board 4 to 6 dE off: the leader kept as patch 1) and
    2 of 8,312 "jumped2" (the first half from the neighbour row) were kept.
    Rule 5 now calls a kept patch within 6 dE of paper paper, and rule 7b
    holds each half against the same half of every other row."""
    rng = np.random.default_rng(100 + seed)
    tries = wrong = 0
    for name, rows in CHARTS.items():
        lab = np.array(rows, float)
        R, N = lab.shape[:2]
        h = N // 2
        for _ in range(2):
            prn = _printed(lab, rng, rng.choice([0, 3, 6, 10]))
            paper = np.array([rng.uniform(92, 97), rng.uniform(-1, 3), rng.uniform(-8, 6)])
            noise = rng.choice([0.3, 1.0, 2.5])
            off = rng.normal(0, 1, 3)
            board = paper + off / np.linalg.norm(off) * rng.uniform(4, 6)
            for exp in range(R):
                cases = [[paper, *prn[exp, 1:], paper, paper, board]]
                for r in (exp - 1, exp + 1):
                    if 0 <= r < R:
                        cases.append([paper, *prn[r, :h], *prn[exp, h:], paper, paper])
                for segs in cases:
                    segs = np.array(segs) + rng.normal(0, noise / np.sqrt(3), (len(segs), 3))
                    n = len(segs)
                    steps = list(rng.normal(40, 4, n))
                    no = [max(4, int(x)) for x in rng.normal(14, 2, n)]
                    for why in (1, 2, 3):
                        tries += 1
                        if ml.decide(segs, steps, no, lab, exp, why)["accept"]:
                            wrong += 1
    assert tries > 5000
    assert wrong == 0


# --- re-check of 5e290544a (2026-11-16), MAJOR-R1: a patch crossed in 3
# readings or fewer (a jerk, a quick lift) was forgiven as an edge sliver
# although the ruler showed a whole patch of travel; the margin then made the
# count, and a patch went missing (review/jerk.py, jerk_drift.py,
# jerk_paper.py). Now a forgiven piece travels at most 0.3 of a patch, and
# rule 0b requires the kept patches to account for the whole distance.

def _jerk_cases(prn, lab, exp, m, rng, trailer, lift0=False):
    """The review's jerk: patches 1..m-1, patch m crossed in 1 to 3 readings
    with its full travel (lift0: with NO ruler travel, the THIRD LOOK's
    lift), the rest, then the trailer form. Both rules."""
    R, N = lab.shape[:2]
    paper = np.array([95.0, 0.5, -3.0])
    out = []
    for rule in ("L", "M"):
        segs = [] if rule == "L" else [(paper, 20, 20)]
        segs += [(prn[exp, i], 14, 13) for i in range(m)]
        segs += [(prn[exp, m], 0 if lift0 else 14, int(rng.integers(1, 4)))]
        segs += [(prn[exp, i], 14, 13) for i in range(m + 1, N)]
        if trailer == "board":
            off = rng.normal(0, 1, 3)
            segs += [(paper, 14, 13), (paper + off / np.linalg.norm(off) * rng.uniform(4, 10), 20, 20)]
        elif trailer == "drift":
            other = prn[exp + 1, N - 1] if exp + 1 < R else prn[exp - 1, N - 1]
            segs += [(other, 14, 13), (paper, 20, 20)]
        else:
            off = rng.normal(0, 1, 3)
            segs += [(paper, 14, 13), (paper + off / np.linalg.norm(off) * rng.uniform(0, 3), 20, 20)]
        labs = np.array([s[0] for s in segs]) + rng.normal(0, 0.3 / np.sqrt(3), (len(segs), 3))
        out.append((labs, [s[1] * rng.uniform(0.9, 1.1) for s in segs], [s[2] for s in segs]))
    return out


@pytest.mark.parametrize("trailer", ["board", "drift", "paper"])
def test_a_patch_jerked_across_is_never_lost(trailer):
    """review/jerk.py (board 4 to 10 dE off paper), jerk_drift.py (one
    coloured piece after the last patch), jerk_paper.py, ported; plus the
    jerk at the FIRST and at the LAST patch."""
    rng = np.random.default_rng({"board": 11, "drift": 12, "paper": 13}[trailer])
    tries = kept = 0
    for name, rows in CHARTS.items():
        lab = np.array(rows, float)
        R, N = lab.shape[:2]
        for pred in (0, 6):
            prn = lab + rng.normal(0, pred / np.sqrt(3), lab.shape)
            for exp in range(R):
                for m in sorted({0, N - 1, *range(1, N - 1, 4)}):
                    for labs, steps, no in _jerk_cases(prn, lab, exp, m, rng, trailer):
                        tries += 1
                        if ml.decide(labs, steps, no, lab, exp, 1)["accept"]:
                            kept += 1
    assert tries > 5000
    assert kept == 0


@pytest.mark.parametrize("trailer", ["board", "drift", "paper"])
def test_the_known_limit_a_lift_the_ruler_did_not_see(trailer):
    """THIRD LOOK at 193fbf176, T1 (review/lift0_jerk*.py, ported): the
    instrument lifted off the ruler, carried over patch m and set down within
    3 readings leaves NO ruler travel there, so rule 0b cannot see the
    missing patch. With paper after the strip rule 5 still sees the margin
    kept as a patch: never kept. With a board or one coloured piece after
    the row it CAN be kept wrongly. The Beta ships with that said (the (i)
    help and the confirmation ask not to lift the instrument). If this test
    ever finds 0 for "board" or "drift", the limit is gone: take the note
    out of the help, the confirmation and the CHANGELOG with it."""
    rng = np.random.default_rng({"board": 21, "drift": 22, "paper": 23}[trailer])
    tries = kept = 0
    for name, rows in CHARTS.items():
        lab = np.array(rows, float)
        R, N = lab.shape[:2]
        for pred in (0, 6):
            prn = lab + rng.normal(0, pred / np.sqrt(3), lab.shape)
            for exp in range(R):
                for m in range(1, N - 1, 4):
                    for labs, steps, no in _jerk_cases(prn, lab, exp, m, rng,
                                                       trailer, lift0=True):
                        tries += 1
                        if ml.decide(labs, steps, no, lab, exp, 1)["accept"]:
                            kept += 1
    assert tries > 5000
    if trailer == "paper":
        assert kept == 0
    else:
        assert 0 < kept < tries * 0.1, (kept, tries)


def test_the_help_and_the_confirmation_say_not_to_lift_the_instrument():
    from ui.dialogs.settings_dialog import (margin_tolerance_confirmation,
                                            margin_tolerance_help)
    for text in (margin_tolerance_help(), margin_tolerance_confirmation()):
        assert "lift" in text and "further along" in text
        assert "can be wrong" in text or "can then be wrong" in text
        assert "ruler diagnostics file" in text


def test_a_lift_with_ruler_travel_but_few_or_no_readings_is_refused():
    """The instrument lifted over patch m: the ruler still travelled (a
    stripe followed by hand), but there are 0 to 3 readings there."""
    lab = np.array(next(iter(CHARTS.values())), float)
    PAPER = _paper(lab)
    N = lab.shape[1]
    U = lab[E]
    for m in (0, 3, N // 2, N - 1):
        rest = [i for i in range(N) if i != m]
        # a margin at the start makes the count right again
        for few in (0, 1, 2, 3):
            segs, steps, no, p0 = [PAPER, PAPER], [40.0, 40.0], [30, 20], [0.0, 40.0]
            pos = 80.0
            for i in range(N):
                if i == m:
                    if few:
                        segs.append(U[i]); steps.append(40.0); no.append(few); p0.append(pos)
                    pos += 40.0
                    continue
                segs.append(U[i]); steps.append(40.0); no.append(14); p0.append(pos)
                pos += 40.0
            segs.append(PAPER); steps.append(40.0); no.append(30); p0.append(pos)
            r = ml.decide(np.array(segs), steps, no, lab, E, 1, p0=p0)
            assert not r["accept"], (m, few, r["why"])
        # and with no piece at all, only the accounting can see it
        segs = [PAPER, PAPER, *U[rest], PAPER]
        p0 = [0.0, 40.0] + [80.0 + 40.0 * i for i in rest] + [80.0 + 40.0 * N]
        r = ml.decide(np.array(segs), [40.0] * len(segs), [30, 20, *([14] * (N - 1)), 30],
                      lab, E, 1, p0=p0)
        assert not r["accept"], (m, r["why"])
        if 0 < m < N - 1:      # inside the row only the accounting sees it
            assert "not explained" in r["why_m"], (m, r["why"])


def test_double_speed_over_two_patches_keeps_nothing_wrong():
    """Two patches crossed at double speed (half the readings, whole travel
    each): an ordinary reading, kept or refused, never wrong."""
    rng = np.random.default_rng(29)
    tries = wrong = kept = 0
    for name, rows in CHARTS.items():
        lab = np.array(rows, float)
        R, N = lab.shape[:2]
        PAPER = _paper(lab)
        for exp in range(R):
            m = int(rng.integers(0, N - 1))
            U = lab[exp] + rng.normal(0, 1.0, (N, 3))
            no = [14] * N
            no[m] = no[m + 1] = int(rng.integers(5, 8))
            segs = np.array([PAPER, PAPER, *U, PAPER])
            r = ml.decide(segs, [40.0] * (N + 3), [30, 30, *no, 30], lab, exp, 2)
            tries += 1
            if r["accept"]:
                kept += 1
                wrong += r["sel"] != list(range(2, N + 2))
    assert wrong == 0
    assert kept > tries // 2


def test_the_accounting_lets_every_correct_recording_of_the_tester_through():
    """The number of rule 0b, measured: in the tester's correct strips the
    largest centre-to-centre step is 1.143 pitches (limit 1.5)."""
    fix = json.loads((DATA / "margin_fixtures.json").read_text(encoding="utf-8"))
    worst = 0.0
    for ss in fix["sessions"]:
        for s in ss["strips"]:
            if s["verdict"] not in ("accepted", "asked") or s["ruler_back"] > 3:
                continue
            c = s["candidates"]
            sg = s["ruler_sign"] or 1
            ds = np.array([sg * x[2] for x in c])
            p0 = np.array([sg * x[6] for x in c])
            med = np.median(ds[1:-1])
            keep = [i for i in range(1, len(c) - 1)
                    if 0.6 * med <= ds[i] <= 1.5 * med and c[i][1] > 3]
            if len(keep) != s["patches"]:
                continue
            dif = np.diff(p0[keep] + ds[keep] / 2)
            big = dif.max()
            worst = max(worst, big / ((dif.sum() - big) / (len(dif) - 1)))
    assert 1.0 < worst < 1.2


def test_a_ruler_that_skipped_a_step_is_never_rescued():
    """Re-check NIT-R3: a change that jumps two positions has no known
    direction; a recording with any is left refused."""
    lab = np.array(next(iter(CHARTS.values())), float)
    PAPER = _paper(lab)
    N = lab.shape[1]
    segs = np.array([PAPER, PAPER, *lab[E], PAPER])
    no = [30, 30, *([14] * N), 30]
    assert ml.decide(segs, [40.0] * (N + 3), no, lab, E, 2)["accept"]
    r = ml.decide(segs, [40.0] * (N + 3), no, lab, E, 2, skipped=1)
    assert not r["accept"] and "skipped" in r["why"]
