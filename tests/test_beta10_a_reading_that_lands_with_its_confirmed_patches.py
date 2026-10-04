"""The size test is waived when a reading lands where its confirmed patches'
readings did (beta 10, Knut #182 5982600086 approving 5982339631).

Knut's O7 (1944-patch run1, limit 60) was red because its error was more than
ΔE 10 shorter than its range's confirmed patches'. But a printer that cannot
reach a colour lands its readings at the same place, its limit: a less vivid
colour asked for has a shorter error and the SAME reading. Knut kept "as large
or larger" and approved waiving it when the patch's MEASURED L*a*b* is within
``LANDING_DE`` (ΔE 15) of a confirmed patch's MEASURED L*a*b*. The other two
tests are unchanged.

A small synthetic printer stands in for his chart here: purple colours asked
for at chroma 70 to 110 all print at chroma 50. On his real data (the replay in
the session notes) red goes 4 -> 0 at limit 60, 10 -> 3 at 50, 19 -> 6 at 40,
and no injected misread more turns yellow.
"""
from __future__ import annotations

import math
import os
import random

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as mm             # noqa: E402
from workflow import patch_flags as PF                      # noqa: E402

BUILT_LANDING_DE = PF.LANDING_DE
HUE = math.radians(300.0)
LIMIT_C = 50.0       # the chroma this printer reaches at this hue
LIMIT_L = 40.0


def _exp(chroma, dh=0.0, L=35.0):
    h = HUE + math.radians(dh)
    return (L, chroma * math.cos(h), chroma * math.sin(h))


def _printed(exp, noise=(0.0, 0.0, 0.0)):
    """What the printer makes of *exp*: clipped to its limit at that hue."""
    h = math.atan2(exp[2], exp[1])
    c = min(math.hypot(exp[1], exp[2]), LIMIT_C)
    return (LIMIT_L + noise[0], c * math.cos(h) + noise[1],
            c * math.sin(h) + noise[2])


#: Three vivid purples, re-read and confirmed: long errors (ΔE ~ 56 to 61).
REFS = {"F17": _exp(105.0, -2.0), "K23": _exp(110.0, 1.0), "V7": _exp(108.0, 3.0)}


def _judge_with_refs(locs=()):
    j = PF.FlagJudge(device_ranges={k: "purple" for k in
                                    list(REFS) + list(locs)})
    for loc, exp in REFS.items():
        m = _printed(exp)
        for _ in range(2):
            v = j.judge(loc, exp, m, math.dist(exp, m), True, strip=loc[0])
        assert v.flag == PF.FLAG_CONFIRMED
    assert j.range_learned("purple")
    return j


def _read(j, loc, exp, meas, standout=None):
    return j.judge(loc, exp, meas, math.dist(exp, meas), True,
                   standout=standout, strip="O")


def test_a_shorter_error_that_lands_at_the_limit_is_learned():
    """O7's case: asked for less, printed the same. Today it would be red
    ("smaller"); with the waiver it is yellow, and says why."""
    j = _judge_with_refs(["O7"])
    exp = _exp(80.0)
    meas = _printed(exp)
    n_ref = min(math.dist(e, _printed(e)) for e in REFS.values())
    assert math.dist(exp, meas) < n_ref - PF.SHIFT_TOLERANCE_DE   # smaller
    v = _read(j, "O7", exp, meas)
    assert v.flag == PF.FLAG_LEARNED and v.landed is True
    assert v.misfit == ()


def test_without_the_waiver_the_same_patch_is_red_and_says_smaller(monkeypatch):
    monkeypatch.setattr(PF, "LANDING_DE", -1.0)
    j = _judge_with_refs(["O7"])
    exp = _exp(80.0)
    v = _read(j, "O7", exp, _printed(exp))
    assert v.flag is PF.FLAG_RED
    assert [m.test for m in v.misfit] == [PF.MISFIT_SMALLER]


def test_a_shorter_error_that_lands_elsewhere_stays_red_with_both_numbers():
    """Same direction, shorter, but its reading is far from theirs: a misread
    is not the printer's limit, and the card gives both sets of numbers."""
    j = _judge_with_refs(["J25"])
    exp = _exp(80.0)
    lim = _printed(exp)
    # Half way from the colour asked for to the limit: same direction, short,
    # and more than ΔE 15 from every confirmed reading.
    meas = tuple(e + 0.5 * (p - e) for e, p in zip(exp, lim))
    v = _read(j, "J25", exp, meas)
    assert v.flag is PF.FLAG_RED
    assert [m.test for m in v.misfit] == [PF.MISFIT_SMALLER]
    m = v.misfit[0]
    want = [math.dist(meas, _printed(e)) for e in REFS.values()]
    assert m.land == (pytest.approx(min(want)), pytest.approx(max(want)))
    assert m.land[0] > PF.LANDING_DE
    assert (m.count, m.total) == (3, 3)


def test_landing_does_not_waive_the_other_two_tests():
    """A reading that lands at the limit but stands out from its strip much
    more than the confirmed patches did stays red: only the size test is
    waived."""
    j = PF.FlagJudge(device_ranges={k: "purple" for k in list(REFS) + ["W1"]})
    for loc, exp in REFS.items():
        m = _printed(exp)
        for _ in range(2):
            j.judge(loc, exp, m, math.dist(exp, m), True, standout=5.0,
                    strip=loc[0])
    exp = _exp(80.0)
    v = _read(j, "W1", exp, _printed(exp), standout=30.0)
    assert v.flag is PF.FLAG_RED
    assert [t.test for t in v.misfit] == [PF.MISFIT_STANDOUT]


def test_a_long_enough_error_is_learned_without_the_waiver():
    j = _judge_with_refs(["X1"])
    exp = _exp(102.0, -6.0)      # more than ΔE 6 from F17: not its peer
    v = _read(j, "X1", exp, _printed(exp))
    assert v.flag == PF.FLAG_LEARNED and v.landed is False


def _replay(limit, landing, readings, monkeypatch):
    monkeypatch.setattr(PF, "LANDING_DE", BUILT_LANDING_DE if landing else -1.0)
    j = PF.FlagJudge(device_ranges={k: "purple" for k in
                                    list(REFS) + list(readings)})
    for loc, exp in REFS.items():
        m = _printed(exp)
        for _ in range(2):
            j.judge(loc, exp, m, math.dist(exp, m), True, strip=loc[0])
    out = {}
    for loc, (exp, meas) in readings.items():
        de = math.dist(exp, meas)
        out[loc] = j.judge(loc, exp, meas, de, de >= limit, live=False,
                           strip="O")      # one strip: no similar patches
    for loc, v in j.rejudge().items():
        out[loc] = v
    return out


def test_the_replay_turns_real_limits_yellow_and_no_misread(monkeypatch):
    """The 1944-patch replay in small: 30 real purples asked for at chroma 70
    to 95 (printed at the limit, ±2 noise) and 30 misreads of them (a smudge:
    20 darker and 40 % less chroma, Knut's simulated fault; or another
    range's reading). Red real patches drop to none; not one misread more is
    yellow than without the waiver."""
    rnd = random.Random(182)
    real, bad = {}, {}
    for i in range(30):
        exp = _exp(rnd.uniform(70.0, 95.0),rnd.uniform(-4.0, 4.0))
        noise = tuple(rnd.uniform(-2.0, 2.0) for _ in range(3))
        real[f"R{i}"] = (exp, _printed(exp, noise))
    for i, (exp, meas) in enumerate(list(real.values())):
        if i % 2:
            wrong = (meas[0] - 20.0, meas[1] * 0.6, meas[2] * 0.6)
        else:
            wrong = (60.0 + rnd.uniform(-5, 5), -40.0, 30.0)   # a green reading
        bad[f"M{i}"] = (exp, wrong)
    for limit in (20.0, 30.0):
        today = _replay(limit, False, {**real, **bad}, monkeypatch)
        built = _replay(limit, True, {**real, **bad}, monkeypatch)
        red_real_today = [k for k in real if today[k].flag is PF.FLAG_RED]
        assert red_real_today, "the synthetic printer must reproduce O7's case"
        assert [k for k in real if built[k].flag is PF.FLAG_RED] == []
        assert all(built[k].landed for k in red_real_today)
        yellow = lambda v: PF.is_yellow(v.flag)                 # noqa: E731
        assert ({k for k in bad if yellow(built[k])}
                == {k for k in bad if yellow(today[k])})


# ---- the cards -----------------------------------------------------------------
@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _rows(info):
    from ui.tiff_preview import _PatchInfoTile
    tile = _PatchInfoTile(None)
    base = {"loc": "O7", "exp_rgb": (90, 30, 200), "meas_rgb": (90, 80, 120),
            "exp_lab": (35, 60, -80), "meas_lab": (40, 20, -25), "de": 64.5,
            "warn": True, "warn_de": 60.0, "colour_range": "purple",
            "range_k": 3, "range_locs": ["BF27", "F17", "K23"]}
    base.update(info)
    tile.set_content(base, "both")
    return [t for _sw, t in tile._rows]


def test_a_yellow_card_learned_by_landing_says_so(qapp):
    rows = _rows({"flag": "learned", "like_loc": "BF27", "landed": True})
    i = rows.index(mm._CARD_RANGE_LEARNED_2)
    assert rows[i + 1:i + 4] == [mm._CARD_RANGE_LANDED_1,
                                 mm._CARD_RANGE_LANDED_2,
                                 mm._CARD_RANGE_LEARNED_3]
    assert "Its reading landed where its" in rows


def test_a_yellow_card_learned_by_size_does_not(qapp):
    rows = _rows({"flag": "learned", "like_loc": "BF27", "landed": False})
    assert mm._CARD_RANGE_LANDED_1 not in rows


def test_the_tab_hands_landed_to_the_card():
    from ui.tabs.tab_measure import TabMeasure
    j = _judge_with_refs(["O7"])
    exp = _exp(80.0)
    x = TabMeasure._verdict_extra(_read(j, "O7", exp, _printed(exp)))
    assert x["flag"] == "learned" and x["landed"] is True


def test_the_new_lines_are_proposed_short_and_dashless():
    msg = mm.CATALOGUE["M-PATCH-COLOUR-RANGE"]
    assert not msg.approved
    for line in (mm._CARD_MISFIT_SMALLER_LIMIT, mm._CARD_MISFIT_LANDED,
                 mm._CARD_MISFIT_LANDED_DE, mm._CARD_RANGE_LANDED_1,
                 mm._CARD_RANGE_LANDED_2):
        assert line in msg.body.split("\n")
        assert len(line) <= 44 and "—" not in line
    assert PF.LANDING_DE == 15.0
