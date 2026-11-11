"""4.3.32 review of feature B: every "cannot tell" rule of the colour check
decides at least one case.

Found in review (2026-11-11) by switching each rule off in turn: the suite
stayed green without the "between" band (score 0.40 to 0.75), without the
lead an accepted file must have over every other arrangement, and without
the per-strip "hardly better than its neighbour" band. Each of them is a
safety margin; a refactor that drops one must turn something red.

The readings are the tester's 624-patch measurement
(`tests/data/turned_colour_check/jctay_624.json`), made deliberately
doubtful: a share of readings scrambled, every reading blended with its
neighbour's, one strip blended with its neighbour's.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import turned_colour_check as C                      # noqa: E402

D = json.loads((Path(__file__).parent / "data" / "turned_colour_check"
                / "jctay_624.json").read_text(encoding="utf-8"))
E = C.expected_lab_rgb(D["rgb"])
M = C.measured_lab(D["xyz"])
ROWS, COLS = D["order_rows"], D["order_columns"]
IDX = np.arange(len(E))


def test_the_untouched_readings_are_cleared():
    assert C.judge(E, M, ROWS, COLS, 4).agrees


def test_a_third_of_the_readings_scrambled_is_between():
    rng = np.random.default_rng(1)
    pick = rng.choice(len(E), int(0.3 * len(E)), replace=False)
    q = IDX.copy()
    q[pick] = rng.permutation(pick)
    j = C.judge(E, M[q], ROWS, COLS, 4)
    assert (j.verdict, j.why) == (C.UNSURE, "between"), j.log_text()
    assert C.DISAGREE_BELOW <= j.score < C.ACCEPT_FROM


def test_readings_that_fit_another_arrangement_nearly_as_well_cannot_tell():
    q = np.roll(IDX, -1)
    j = C.judge(E, 0.6 * M + 0.4 * M[q], ROWS, COLS, 4)
    assert (j.verdict, j.why) == (C.UNSURE, "other-arrangement"), j.log_text()
    assert j.score >= C.ACCEPT_FROM


def test_a_strip_hardly_better_than_its_neighbour_cannot_tell():
    js = np.array([k * ROWS + 20 for k in range(COLS)])
    M2 = M.copy()
    M2[js] = 0.6 * M[js] + 0.4 * M[np.roll(js, -1)]
    j = C.judge(E, M2, ROWS, COLS, 4)
    assert (j.verdict, j.why, j.strip) == (C.UNSURE, "strip-unclear", 20), \
        j.log_text()
