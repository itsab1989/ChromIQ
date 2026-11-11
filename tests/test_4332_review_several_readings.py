"""4.3.32 review, pass 2: several readings must never name the wrong one
because of how they were counted, and a verdict says only what was measured.

* THE SAME READING TWICE. Three readings of which two are one file (added
  twice, or the measurement itself added again) put each patch's centre on
  that file: the GOOD reading was then said to "stand apart" on every patch
  and to "differ overall", and the bad one, counted twice, "agreed with the
  others". A reading that repeats one already compared, value for value, is
  now refused with M-READINGS-UNUSABLE and the rest are compared without it.
* "AGREES WITH THE OTHERS" WAS NOT ALWAYS TRUE. The verdict is about the
  centre: three readings at L* +0, +0.9 and +1.8 are each within 1.0 of the
  centre (the middle one), while readings 1 and 3 differ by 1.8. The verdict
  now says "within the tolerance of the centre on every patch".

Independent arithmetic (centre, distance, spread) was checked against
`ti3_analysis.ciede2000` on synthetic readings: equal to 1e-14.
"""
from __future__ import annotations

import itertools
import os
from pathlib import Path

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M                  # noqa: E402
from workflow.reading_compare import Reading, compare_several   # noqa: E402
from workflow.ti3_analysis import ciede2000                     # noqa: E402

N = 60
_rng = np.random.default_rng(0)
BASE = np.c_[_rng.uniform(20, 90, N), _rng.uniform(-50, 50, N),
             _rng.uniform(-50, 50, N)]
DEV = _rng.uniform(0, 100, (N, 3))


def _rd(name: str, lab) -> Reading:
    return Reading(Path(name), [str(i + 1) for i in range(N)], [""] * N,
                   DEV.copy(), np.asarray(lab, dtype=float))


def _noisy(seed: int, shift=(0.0, 0.0, 0.0)):
    return BASE + np.random.default_rng(seed).normal(0, 0.15, BASE.shape) \
        + np.asarray(shift)


def test_the_arithmetic_matches_an_independent_one():
    rs = [_rd(f"r{k}", _noisy(k, (2.0 if k == 3 else 0, 0, 0)))
          for k in range(4)]
    c, refused = compare_several(rs[0], rs[1:])
    assert not refused
    lab = np.stack([r.lab for r in rs])
    centre = np.median(lab, axis=0)
    dev = [[ciede2000(tuple(lab[k, i]), tuple(centre[i])) for i in range(N)]
           for k in range(4)]
    spread = [max(ciede2000(tuple(lab[i, p]), tuple(lab[j, p]))
                  for i, j in itertools.combinations(range(4), 2))
              for p in range(N)]
    assert np.allclose(c.dev, dev, atol=1e-9)
    assert np.allclose(c.spread, spread, atol=1e-9)


def test_a_bad_reading_added_twice_does_not_outvote_the_good_one():
    good, bad = _noisy(1), _noisy(1, (3.0, 0, 0))
    m = _rd("measurement.ti3", good)
    c, refused = compare_several(
        m, [_rd("second.ti3", _noisy(2)), _rd("bad.ti3", bad),
            _rd("bad copy.ti3", bad.copy())])
    assert [r.path.name for r, _e in refused] == ["bad copy.ti3"]
    exc = refused[0][1]
    assert exc.message is M.M_READINGS_UNUSABLE
    assert "bad.ti3" in exc.reason and "same reading again" in exc.reason
    assert c.r == 3
    apart = c.stands_apart(1.0)
    # the bad reading (index 2) is the one that stands apart, never 0 or 1
    assert set(apart[apart >= 0].tolist()) == {2}
    assert c.verdict(0, 1.0).kind == "agrees"


def test_the_measurement_added_again_is_refused():
    bad, good = _noisy(1, (3.0, 0, 0)), _noisy(2)
    m = _rd("measurement.ti3", bad)
    c, refused = compare_several(
        m, [_rd("measurement again.ti3", bad.copy()), _rd("good.ti3", good),
            _rd("third.ti3", _noisy(3))])
    assert [r.path.name for r, _e in refused] == ["measurement again.ti3"]
    assert "measurement.ti3" in refused[0][1].reason
    apart = c.stands_apart(1.0)
    assert set(apart[apart >= 0].tolist()) == {0}


def test_two_files_left_after_a_duplicate_are_no_several_comparison():
    good = _noisy(1)
    c, refused = compare_several(
        _rd("m.ti3", good), [_rd("b.ti3", _noisy(2)),
                             _rd("m copy.ti3", good.copy())])
    assert c is None and len(refused) == 1


def test_the_agrees_verdict_claims_only_the_centre(qapp):
    """+0, +0.9, +1.8 in L*: every reading is within 1.0 of the centre,
    readings 1 and 3 are 1.8 apart. The words must not say they agree."""
    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    from workflow.reading_compare import Verdict
    base = _noisy(1)
    c, _r = compare_several(
        _rd("m", base), [_rd("b", base + [0.9, 0, 0]),
                         _rd("c", base + [1.8, 0, 0])])
    assert all(c.verdict(k, 1.0).kind == "agrees" for k in range(3))
    assert float(c.pair[0, 2].min()) > 1.0
    text = Ti3InfoDialog._verdict_text(Verdict("agrees"))
    assert "centre" in text and "others" not in text
