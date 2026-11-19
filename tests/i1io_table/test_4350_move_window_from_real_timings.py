"""4.3.50 (the first complete page on a real i1iO 2, 19 Nov 2026): the time window of a computed
move, corrected from REAL timings.

``data/real_table_moves.json`` holds, as numbers only, every computed m0 of that page (545, in
the order sent) and the m0 lines of i1Profiler's own recorded sessions on the same model (557, in
9 sessions): where the arm was read before, the target, the time to the done answer, where it was
read after.

What they show:

* A move of 0 to 3 units (the larger axis) is answered at once: 0.015-0.016 s, in 24 of 24 cases
  (the real page's 3-unit move included). From 4 units on the arm really travels (4-6 units:
  0.111-0.112 s). Whether a move of 4 to 10 units to a target the table was ALREADY sent to (the
  same target sent again after an arrival a few units short) is also answered at once is not
  recorded. The window's lower limit was 0.75 t - 0.05, which passes 0.016 s only up to 3 units:
  such a move would have been stopped as "outside its time window" although nothing was wrong.
* The time follows the straight-line distance, not the larger axis: over the 985 moves longer
  than 60 units, took / predicted is 1.006-1.068 with the straight line and 1.006-1.186 with the
  larger axis (the real page's long diagonal: 2.528 s, predicted 2.279 s).

So: no lower limit up to ``geo.SMALL_MOVE_UNITS`` (10 units, every arrival miss the job tolerates
or moves to once more); above it, the lower limit as before on the straight-line prediction; the
upper limit unchanged in form, on the straight-line prediction.
"""
from __future__ import annotations

import json
import math

from tests.i1io_table.job_harness import HERE
from workflow.i1io.table import geometry as geo

DATA = json.loads((HERE / "data" / "real_table_moves.json").read_text(encoding="utf-8"))
REAL = DATA["real_run_2026_11_19"]
RECORDED = [m for s in DATA["recorded_sessions"] for m in s]
ALL = REAL + RECORDED
#: the real "answered at once" time (0.015-0.016 s in every case), with one clock tick of slack
AT_ONCE_S = 0.016


def _win(m):
    return geo.move_window((m[0], m[1]), (m[2], m[3]), m[4])


def test_the_data_is_what_this_file_says():
    assert len(REAL) == 545 and len(RECORDED) == 557 and len(DATA["recorded_sessions"]) == 9
    small = [m for m in ALL if max(abs(m[2] - m[0]), abs(m[3] - m[1])) <= 3]
    assert len(small) == 24 and all(m[5] <= AT_ONCE_S for m in small)
    four_to_six = [m for m in ALL if 4 <= max(abs(m[2] - m[0]), abs(m[3] - m[1])) <= 6]
    assert four_to_six and all(0.11 <= m[5] <= 0.113 for m in four_to_six)


def test_every_real_and_recorded_move_finished_inside_its_window():
    out = [m for m in ALL if not _win(m)[0] <= m[5] <= _win(m)[1]]
    assert out == []


def test_a_move_of_up_to_ten_units_answered_at_once_is_not_a_fault():
    """The false stop: the same target sent again from a reading a few units short (as after a
    5 mm step that arrived 5 units short, i1Profiler's own arrivals reach dy -5) may be answered
    in 0.016 s, as every real move of up to 3 units was. Before 4.3.50 the lower limit was above
    0.016 s from 4 units on, so the job stopped such a move as outside its time window."""
    for d in range(0, geo.SMALL_MOVE_UNITS + 1):
        for a, b in (((0, 3000), (d, 3000)), ((0, 3000), (0, 3000 + d)),
                     ((0, 3000), (d, 3000 + d))):
            lo, hi = geo.move_window(a, b)
            assert lo == 0.0 <= AT_ONCE_S <= hi, (d, lo, hi)


def test_the_upper_limit_still_catches_a_move_that_does_not_finish():
    # a tiny move: the same 0.7 s floor as before; a long one: 1.35 t + 0.35 as before
    assert geo.move_window((0, 0), (3, 0))[1] == 0.7
    lo, hi = geo.move_window((1248, 1593), (-1350, 3371))
    t = geo.predicted_move_time((1248, 1593), (-1350, 3371))
    assert hi == 1.35 * t + 0.35 and hi < 3.8
    # beyond the small moves the lower limit is kept (an answer far too soon is still caught)
    lo, _hi = geo.move_window((0, 0), (geo.SMALL_MOVE_UNITS + 1, 0))
    assert lo > 0.0


def test_the_time_follows_the_straight_line():
    """Over every real and recorded move longer than 60 units the prediction is at most 1 % too
    long and at most 7 % too short."""
    long_ = [m for m in ALL if max(abs(m[2] - m[0]), abs(m[3] - m[1])) > 60]
    assert len(long_) == 985
    ratios = [m[5] / geo.predicted_move_time((m[0], m[1]), (m[2], m[3]), m[4]) for m in long_]
    assert min(ratios) >= 0.99 and max(ratios) <= 1.07, (min(ratios), max(ratios))
    # the real page's long diagonal to the first row (2598 x 1778 units): 2.528 s
    diag = [m for m in REAL if abs(m[2] - m[0]) > 2500 and abs(m[3] - m[1]) > 1700]
    assert diag and all(abs(m[5] - geo.predicted_move_time((m[0], m[1]), (m[2], m[3]))) < 0.05
                        for m in diag)


def test_the_prediction_is_the_straight_line_triangle():
    for (a, b) in (((0, 0), (300, 400)), ((0, 0), (3000, 0)), ((10, 10), (10, 10))):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        want = max(2.0 * math.sqrt(d / geo.ACCEL), 0.015) if d <= 4500 else d / 3000 + 1.5
        assert abs(geo.predicted_move_time(a, b) - want) < 1e-9
