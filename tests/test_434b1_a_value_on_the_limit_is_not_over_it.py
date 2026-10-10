"""A value ON a threshold is not over it: every test of Preferences ▸
Measurement compares at one decimal (#182, Knut 6094941512, 4.3.4 beta 1).

Knut, on beta 17: "patch B3 turned red with 3.0 dE error from its
neighbours. This is ON the error threshold of 3.0, which should not be red,
because errors shall happen if ABOVE the threshold ... the values being
compared with the threshold is rounded to the closest value with one decimal
(0.1 steps). This principle should apply for all measurement thresholds and
tests (as defined in preferences -> measurement tab)".

One helper decides it (``workflow.misread_settings``): ``above`` for a
limit (the Patch error limit, the Neighbour limit, the strip test's fence),
``within`` for a radius or a tolerance (the Colour-neighbour radius, the
Same-reading tolerance). Both round exactly as the cards print (``.1f``), so
what a card shows is what was compared; proved here value by value.
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from workflow import misread_settings as MS  # noqa: E402
from workflow import patch_flags as pf  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))


# ---- the helper ------------------------------------------------------------

@pytest.mark.parametrize("value, limit, over", [
    (3.0, 3.0, False), (3.1, 3.0, True), (3.04, 3.0, False),
    (3.06, 3.0, True), (2.96, 3.0, False), (95.0, 95.0, False),
    (95.04, 95.0, False), (95.1, 95.0, True), (0.0, 0.5, False),
])
def test_above_is_above_at_one_decimal(value, limit, over):
    assert MS.above(value, limit) is over
    assert MS.within(value, limit) is (not over)


def test_the_rounding_is_the_cards_own():
    """What a card prints (``f"{v:.1f}"``) is exactly what is compared, for
    every value, ties and near-ties included."""
    rng = random.Random(6094941512)
    values = [rng.uniform(0, 200) for _ in range(20000)]
    values += [k / 100 for k in range(0, 2000)]          # every x.x5 tie
    values += [k / 20 + d for k in range(0, 400)
               for d in (-1e-12, 0.0, 1e-12)]
    for v in values:
        shown = f"{v:.1f}"
        assert MS.one_decimal(v) == float(shown)
        for lim in (3.0, 5.0, 10.0, 95.0):
            assert MS.above(v, lim) is (float(shown) > lim)


def test_the_array_form_rounds_the_same_way():
    import numpy as np
    rng = random.Random(1)
    vals = np.array([rng.uniform(13, 17) for _ in range(5000)]
                    + [k / 100 for k in range(1300, 1700)]
                    + [15.05 - 1e-13, 15.05, 15.05 + 1e-13, np.inf, np.nan])
    got = MS.within_array(vals.reshape(-1, 1), 15.0).ravel()
    want = [MS.within(float(v), 15.0) if np.isfinite(v) else False
            for v in vals]
    assert got.tolist() == want


# ---- the Patch error limit and the strip test, in the Measure tab ----------

from test_neighbour_check_in_the_measure_tab import (  # noqa: E402
    _card, _flags, _info, _strip, _tab, _text)


def _strip_with(letter, des):
    """A strip whose patches report these ΔE*ab (the engine's own figure,
    the one the limit is judged on)."""
    ev = _strip(letter)
    for p, de in zip(ev["patches"], des):
        p["de"] = de
    return ev


@pytest.mark.parametrize("de, red", [(5.0, False), (5.04, False),
                                     (5.05000001, True), (5.1, True),
                                     (4.9, False)])
def test_the_patch_error_limit_on_the_limit_is_not_red(qapp, tmp_path, de,
                                                       red):
    """Limit 5.0, strip test and neighbour check off: ΔE 5.0 is not red,
    5.1 is; and the red card prints a ΔE above the limit it prints."""
    tab = _tab(tmp_path, settings={"patch_read_warn_de_estimated": 5.0,
                                   "patch_strip_test_estimated": False,
                                   "patch_neighbour_check": False})
    tab._on_strip_measured(_strip_with("A", [de] + [1.0] * 11))
    assert (_flags(tab)["A1"] is True) is red
    info = _info(tab, "A1")
    assert bool(info["warn"]) is red
    if red:
        text = _text(_card(info))
        shown = f"{de:.1f}"
        assert f"ΔE*ab {shown} reached the patch error limit (5.0" in text
        assert float(shown) > 5.0


def test_the_card_never_shows_a_red_patch_at_or_under_its_limit(qapp,
                                                                tmp_path):
    """A patch is outlined by the limit exactly when its printed ΔE is above
    the printed limit: the card and the outline agree at every value from
    4.80 to 5.20."""
    des = [round(4.80 + 0.01 * i, 2) for i in range(41)]
    tab = _tab(tmp_path, settings={"patch_read_warn_de_estimated": 5.0,
                                   "patch_strip_test_estimated": False,
                                   "patch_neighbour_check": False})
    for i in range(0, len(des), 12):
        chunk = des[i:i + 12]
        letter = "ABCDEF"[i // 12]
        tab._on_strip_measured(_strip_with(letter, chunk + [1.0] * (
            12 - len(chunk))))
        for n, de in enumerate(chunk, start=1):
            loc = f"{letter}{n}"
            # outlined (red, or yellow once similar patches of other strips
            # confirm it) exactly when the printed ΔE is above 5.0
            info = _info(tab, loc)
            over = float(f"{de:.1f}") > 5.0
            assert bool(info["warn"]) is over, (loc, de)
            assert bool(_flags(tab)[loc]) is over, (loc, de)


def test_the_strip_test_fence_is_compared_the_same_way():
    """The strip test: a patch past the limit is red only when it is ALSO
    above its strip's fence, at one decimal; a fence of 0 is the test off."""
    from ui.tabs.tab_measure import _past_limit
    assert _past_limit(10.0, 5.0, 10.0) is False      # on the fence
    assert _past_limit(10.04, 5.0, 10.0) is False
    assert _past_limit(10.1, 5.0, 10.0) is True
    assert _past_limit(10.1, 10.1, 0.0) is False      # on the limit
    assert _past_limit(10.2, 10.1, 0.0) is True       # strip test off


def test_patch_by_patch_the_limit_is_compared_the_same_way(qapp, tmp_path):
    tab = _tab(tmp_path, settings={"patch_read_warn_de_estimated": 5.0,
                                   "patch_neighbour_check": False})
    for loc, de in (("A1", 5.0), ("A2", 5.1)):
        p = next(x for x in _strip("A")["patches"] if x["loc"] == loc)
        tab._on_patch_measured({**p, "de": de})
    assert _flags(tab)["A1"] is not True
    assert _flags(tab)["A2"] is True


def test_the_out_of_tolerance_sound_follows_the_outline(qapp, tmp_path,
                                                        monkeypatch):
    import core.sound as snd
    tab = _tab(tmp_path, settings={"patch_read_warn_de_estimated": 5.0})
    played = []
    monkeypatch.setattr(tab._sound, "play", played.append)
    tab._on_patch_sound({"loc": "A1", "de": 5.0})
    tab._on_patch_sound({"loc": "A1", "de": 5.1})
    assert played == [snd.PATCH_OK, snd.PATCH_OUT_OF_TOL]


# ---- the neighbour check: the limit and the radius --------------------------

def _nc(rows, **kw):
    from workflow.neighbour_check import NeighbourCheck
    nc = NeighbourCheck(**kw)
    for loc, exp, meas, strip in rows:
        nc.set_reading_lab(loc, exp, meas, strip)
    nc.evaluate()
    return nc


@pytest.mark.parametrize("dist, neighbour", [(15.0, True), (15.04, True),
                                             (15.06, False), (15.1, False)])
def test_a_patch_on_the_colour_neighbour_radius_is_a_neighbour(dist,
                                                               neighbour):
    """Radius 15.0: a patch whose expected colour is 15.0 away is within
    it; 15.1 is not."""
    rows = [("A1", (50, 0, 0), (50, 0, 0), "A"),
            ("B1", (50 + dist, 0, 0), (50 + dist, 0, 0), "B")]
    f = _nc(rows, radius=15.0).finding("A1")
    assert (f is not None and "B1" in f.compared) is neighbour


def test_the_neighbour_card_shows_the_figure_it_was_judged_on(qapp,
                                                              tmp_path):
    """Knut's B3: a patch 3.0 further from its expected colour than its
    neighbours, at a Neighbour limit of 3.0, is not red, and its card says
    "ΔE 3.0 further" with no red line."""
    from workflow.neighbour_check import NeighbourCheck
    rows = [("A1", (50, 0, 0), (47.0, 0, 0), "A"),
            ("B1", (50, 1, 0), (50, 1, 0), "B"),
            ("C1", (50, 2, 0), (50, 2, 0), "C")]
    nc = NeighbourCheck(limit=3.0)
    for r in rows:
        nc.set_reading_lab(*r)
    nc.evaluate()
    n, further = nc.comparison("A1")
    assert f"{further:.1f}" == "3.0" and not nc.is_suspect("A1")
    nc.set_reading_lab("A1", (50, 0, 0), (46.9, 0, 0), "A")
    nc.evaluate()
    assert f"{nc.comparison('A1')[1]:.1f}" == "3.1" and nc.is_suspect("A1")


# ---- the Same-reading tolerance, and the re-read rules' limit --------------

def _rereads(offset, *, limit=95.0, first_de=100.0, second_de=100.0,
             flagged=True):
    """A patch read past the limit, then read again *offset* ΔE*ab away."""
    j = pf.FlagJudge()
    j.set_same_reading_de(3.0)
    exp = (50.0, 0.0, 0.0)
    j.judge("A1", exp, (40.0, 0.0, 0.0), first_de, True, strip="A",
            limit=limit)
    return j.judge("A1", exp, (40.0 + offset, 0.0, 0.0), second_de, flagged,
                   strip="A", limit=limit)


def test_a_re_read_on_the_tolerance_is_the_same_reading():
    """Same-reading tolerance 3.0: a re-read 3.0 away is the same colour
    (yellow), 3.1 away is not (red, and the card asks for another)."""
    assert _rereads(3.0).flag == pf.FLAG_CONFIRMED
    assert _rereads(3.04).flag == pf.FLAG_CONFIRMED      # prints 3.0
    v = _rereads(3.1)
    assert v.flag is pf.FLAG_RED and v.unsettled


def test_a_re_read_on_the_limit_is_under_it():
    """(d) of Knut 6045500910 with his new rule: a re-read ON the limit
    (95.0 at 95.0) is not past it, so the misread past it was corrected;
    and an earlier reading on the limit was never past it."""
    v = _rereads(10.0, second_de=95.0, flagged=False)
    assert pf.is_corrected(v.flag)
    v = _rereads(10.0, first_de=95.0, second_de=100.0)
    assert not v.unsettled
