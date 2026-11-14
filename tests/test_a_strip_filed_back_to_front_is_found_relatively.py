"""4.3.37: a whole strip filed back to front is found RELATIVELY.

A tester's i1Pro 3 measurement (a chart in plain order, ChromIQ 4.3.36):
strip 9 was filed back to front by the reader's recognition (with
bidirectional recognition on, a strip filed under the expected row can take
the direction of another row that matched better), 48-66 ΔE00 off. ChromIQ's
own back-to-front check asked the turned-round fit to be GOOD in absolute
terms (35 ΔE76 against the design colours) and missed it: turned round it was
still 46.9 from the design colours, because no printer prints the design
colours (as filed: 104.1). The same happens to a strip scanned last to first
with bidirectional recognition switched OFF (-B): the reader files it as
read, and with -S (ChromIQ's default) nothing warns.

workflow/slipped_strip.py now also judges the whole strip relatively: turned
round at most half as far, at least 20 ΔE76 better, most patches better. The
fixtures here are synthetic, with the shape of that file (no tester data is
in the repository).
"""
from __future__ import annotations

import random

import pytest

from workflow import slipped_strip as ss


def _lab_strip(rng, n=12, smooth=False):
    """Design colours of one strip: random (a shuffled chart) or a strip of a
    chart in plain order (neighbours closer, the ends far apart)."""
    if not smooth:
        return [(rng.uniform(15, 95), rng.uniform(-60, 60), rng.uniform(-60, 60))
                for _ in range(n)]
    a0, b0 = rng.uniform(-60, 60), rng.uniform(-60, 60)
    a1, b1 = rng.uniform(-60, 60), rng.uniform(-60, 60)
    return [(20 + 70 * i / (n - 1),
             a0 + (a1 - a0) * i / (n - 1) + rng.uniform(-8, 8),
             b0 + (b1 - b0) * i / (n - 1) + rng.uniform(-8, 8))
            for i in range(n)]


def _printed(rng, design, err=(18.0, 30.0)):
    """What a real printer gives for the design colours: each patch 18-30
    ΔE76 away (a correctly read real strip is 10-26 ΔE from its design)."""
    out = []
    for L, a, b in design:
        d = rng.uniform(*err)
        v = [rng.gauss(0, 1) for _ in range(3)]
        k = d / max(1e-6, sum(x * x for x in v) ** 0.5)
        out.append((L + v[0] * k * 0.4, a + v[1] * k, b + v[2] * k))
    return out


def _tester_like(rng):
    """A strip shaped like the tester's strip 9: the ends of a strip in
    plain order far apart (mirror distance about 110 ΔE76), printed 18-30
    from the design."""
    design = [(15 + 75 * i / 11, -55 + 110 * i / 11, 50 - 100 * i / 11)
              for i in range(12)]
    # his printer sat 40-50 ΔE76 from the design colours on this strip
    # (turned round: 46.9), beyond the old absolute limit of 35
    return design, _printed(rng, design, err=(40.0, 52.0))


def test_the_testers_case_is_found_although_turned_round_is_not_good():
    rng = random.Random(150222)
    design, printed = _tester_like(rng)
    filed = list(reversed(printed))           # filed back to front
    run = ss.find_slipped_run(filed, design)
    assert run is not None and run.reversed and run.offset == 0
    assert (run.first, run.last) == (0, 11)
    # the old, absolute rule alone did not find it
    assert run.shifted_de > ss.GOOD_DE
    assert run.shifted_de <= ss.REV_RATIO * run.base_de


def test_a_strip_scanned_last_to_first_with_bidirectional_off_is_found():
    """-B: the reader tries only the forward direction and files a strip
    scanned from the last patch to the first as it was read. That is the
    same as filed back to front, and is found the same way."""
    rng = random.Random(4337)
    hits = 0
    for _ in range(200):
        design = _lab_strip(rng, smooth=True)
        printed = _printed(rng, design)       # an ordinary printer
        scanned_backwards = printed[::-1]     # what the reader stores
        run = ss.find_slipped_run(scanned_backwards, design)
        hits += bool(run and run.reversed)
    # measured: 198 of 200; the two misses are strips whose two halves are
    # too alike to tell from their reverse (random ramps with close ends)
    assert hits >= 196, hits


def test_a_printer_far_from_the_design_is_still_found_nearly_always():
    """The tester's own shape (printed 40-52 from the design): the relative
    rule's limit, measured, not assumed."""
    rng = random.Random(150223)
    hits = 0
    for _ in range(500):
        design, printed = _tester_like(rng)
        run = ss.find_slipped_run(printed[::-1], design)
        hits += bool(run and run.reversed)
    assert hits >= 0.95 * 500, hits


@pytest.mark.parametrize("smooth", [False, True])
def test_no_false_alarm_on_strips_read_the_right_way(smooth):
    """Honest strips, printed 18-30 ΔE76 away from their design: a shuffled
    chart and a chart in plain order, 3000 strips each."""
    rng = random.Random(1 if smooth else 2)
    alarms = 0
    for _ in range(3000):
        design = _lab_strip(rng, smooth=smooth)
        run = ss.find_slipped_run(_printed(rng, design), design)
        alarms += bool(run and run.reversed and run.offset == 0
                       and run.run_first == 0 and run.run_last == 11)
    assert alarms == 0


def test_a_strip_that_reads_the_same_both_ways_is_never_called_turned():
    """A symmetric strip (each colour equals its mirror's) cannot be told
    from its reverse: never flagged."""
    rng = random.Random(7)
    half = _lab_strip(rng, n=6)
    design = half + half[::-1]
    printed = _printed(rng, design)
    run = ss.find_slipped_run(printed[::-1], design)
    assert not (run and run.reversed and run.offset == 0
                and run.base_de >= ss.TRIGGER_DE
                and run.shifted_de <= ss.REV_RATIO * run.base_de
                and run.run_first == 0 and run.run_last == 11
                and run.shifted_de > ss.GOOD_DE)


def test_the_rule_is_relative_and_written_down():
    src = open(ss.__file__, encoding="utf-8").read()
    assert "REV_RATIO = 0.5" in src and "REV_MIN_GAIN = 20.0" in src
    assert "def _turned_round(" in src


def test_the_question_names_every_cause_and_says_what_was_found():
    """4.3.37 review (M5): M-STRIP-REVERSED no longer blames a slip alone."""
    from workflow import measurement_messages as M
    assert M.M_STRIP_REVERSED.id in M.PROPOSED          # still a proposal
    body = M.M_STRIP_REVERSED.body
    assert "looks much like another strip of the chart" in body
    assert "Bidirectional disabled (-B)" in body
    assert "this strip matches the chart far better turned round" in body
