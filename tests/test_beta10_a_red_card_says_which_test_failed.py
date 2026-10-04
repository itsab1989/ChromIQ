"""A red patch in a LEARNED range says which test ruled it out (beta 10).

Knut, #182 5982038838, asked about O7 on his 1944-patch chart at limit 60:
*"What does it mean 'but this one is off in a different way'? How different?
and why is that not defined exactly?"* The answer (5982058944) was that O7
failed the "as large or larger" test (ΔE 64 against 75 to 92), and he approved
the card naming the test and its numbers (5982206917, answer 1).

These tests pin that the judge reports the test(s) that ruled a patch out
without changing a single outline, that the card says it in M-PATCH-COLOUR-
RANGE's words, and that dropping the size test (Knut's open question 2,
5982217410) is the one constant ``PATCH_SIZE_TEST``.
"""
from __future__ import annotations

import math
import os
import random

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as mm             # noqa: E402
from workflow import patch_flags as PF                      # noqa: E402

#: A purple the printer falls short of, like Knut's O7 range: the error points
#: back toward grey and is long.
EXP = {"F17": (35.0, 60.0, -80.0), "K23": (36.0, 62.0, -78.0),
       "V7": (34.0, 58.0, -82.0)}
SHIFT = (5.0, -40.0, 55.0)           # |SHIFT| ~ 68.2


def _meas(exp, shift):
    return tuple(e + s for e, s in zip(exp, shift))


def _learned_judge(standout=None):
    """A judge whose 'purple' range has learned from three re-read patches,
    each off by SHIFT (and standing *standout* above its strip)."""
    j = PF.FlagJudge(device_ranges={k: "purple" for k in
                                    list(EXP) + ["O7", "J25", "W1"]})
    de = PF._norm(SHIFT)
    for loc, exp in EXP.items():
        for _ in range(2):
            v = j.judge(loc, exp, _meas(exp, SHIFT), de, True,
                        standout=standout, strip=loc[0])
        assert v.flag == PF.FLAG_CONFIRMED
    assert j.range_learned("purple")
    return j


#: A probe's expected colour: the same range, but more than ΔE 6 from every
#: confirmed patch, so it is never their similar patch (10.3a).
PROBE = (35.0, 70.0, -70.0)


def _judge(j, loc, shift, standout=None):
    exp = PROBE
    return j.judge(loc, exp, _meas(exp, shift), PF._norm(shift), True,
                   standout=standout, strip="O")


def test_a_smaller_error_says_smaller_with_its_numbers():
    """O7's case: same direction, much shorter."""
    j = _learned_judge()
    v = _judge(j, "O7", tuple(0.7 * s for s in SHIFT))
    assert v.flag is PF.FLAG_RED and v.range_k == 3
    assert [m.test for m in v.misfit] == [PF.MISFIT_SMALLER]
    m = v.misfit[0]
    n = PF._norm(SHIFT)
    assert m.own[0] == pytest.approx(0.7 * n, abs=1e-6)
    assert m.ref == (pytest.approx(n), pytest.approx(n))
    assert (m.count, m.total) == (3, 3)
    assert m.gap == pytest.approx(n - PF.SHIFT_TOLERANCE_DE - 0.7 * n)


def test_an_error_pointing_another_way_says_sideways():
    j = _learned_judge()
    turned = (SHIFT[0] + 20.0, SHIFT[1], SHIFT[2])          # 20 sideways-ish
    v = _judge(j, "J25", turned)
    assert v.flag is PF.FLAG_RED
    assert [m.test for m in v.misfit] == [PF.MISFIT_SIDEWAYS]
    assert v.misfit[0].own[0] > PF.SHIFT_TOLERANCE_DE


def test_a_patch_standing_out_more_says_standout():
    j = _learned_judge(standout=30.0)
    v = _judge(j, "W1", SHIFT, standout=50.0)
    assert v.flag is PF.FLAG_RED
    assert [m.test for m in v.misfit] == [PF.MISFIT_STANDOUT]
    m = v.misfit[0]
    assert m.own == (50.0, 50.0) and m.ref == (30.0, 30.0)


def test_a_like_patch_is_learned_and_carries_no_misfit():
    j = _learned_judge()
    v = _judge(j, "O7", SHIFT)
    assert v.flag == PF.FLAG_LEARNED and v.misfit == ()


def test_the_fewest_tests_that_cover_every_confirmed_patch():
    """One confirmed patch ruled out sideways only, two by size only: both
    tests are named, size first (it rules out more), and each says how many
    of the confirmed patches it ruled out."""
    j = PF.FlagJudge(device_ranges={k: "purple" for k in
                                    ["A1", "B1", "C1", "D1"]})
    long_ = (0.0, -60.0, 60.0)
    other = (0.0, 10.0, 10.0)                  # short, at right angles
    for loc, shift in (("A1", long_), ("B1", long_), ("C1", other)):
        exp = (40.0, 60.0, -70.0)
        for _ in range(2):
            j.judge(loc, exp, _meas(exp, shift), PF._norm(shift), True,
                    strip=loc[0])
    probe = (0.0, -15.0, 25.0)   # short of long_, and ~22 sideways of other
    exp = (40.0, 60.0, -70.0)
    v = j.judge("D1", exp, _meas(exp, probe), PF._norm(probe), True, strip="D")
    assert v.flag is PF.FLAG_RED
    tests = [m.test for m in v.misfit]
    assert tests[0] == PF.MISFIT_SMALLER and PF.MISFIT_SIDEWAYS in tests
    assert v.misfit[0].count < v.misfit[0].total


def test_reporting_never_changes_an_outline():
    """Over many random patches: red with numbers exactly when _like finds no
    confirmed patch it is like; the flag is what _like alone decides."""
    rnd = random.Random(182)
    for i in range(200):
        j = _learned_judge(standout=20.0)       # each probe on its own
        shift = tuple(s * rnd.uniform(0.4, 1.4) + rnd.uniform(-15, 15)
                      for s in SHIFT)
        so = rnd.uniform(0.0, 45.0)
        exp = (PROBE[0] + rnd.uniform(-3, 3), PROBE[1], PROBE[2])
        v = j.judge("O7", exp, _meas(exp, shift), PF._norm(shift), True,
                    standout=so, strip="O")
        like = j._like("purple", exp, shift, so)
        assert (v.flag == PF.FLAG_LEARNED) is (like is not None)
        assert bool(v.misfit) is (like is None)


def test_dropping_the_size_test_is_one_constant(monkeypatch):
    """Knut's question 2 (5982217410): with PATCH_SIZE_TEST off, O7's case
    turns yellow, and no card can say "smaller" any more."""
    monkeypatch.setattr(PF, "PATCH_SIZE_TEST", False)
    j = _learned_judge()
    v = _judge(j, "O7", tuple(0.7 * s for s in SHIFT))
    assert v.flag == PF.FLAG_LEARNED
    turned = (SHIFT[0] + 20.0, 0.5 * SHIFT[1], 0.5 * SHIFT[2])
    v = _judge(j, "J25", turned)
    assert v.flag is PF.FLAG_RED
    assert PF.MISFIT_SMALLER not in [m.test for m in v.misfit]


# ---- the card -----------------------------------------------------------------
@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _card(qapp, misfit):
    from ui.tiff_preview import _PatchInfoTile
    tile = _PatchInfoTile(None)
    tile.set_content({"loc": "O7", "exp_rgb": (90, 30, 200),
                      "meas_rgb": (90, 80, 120), "exp_lab": (35, 60, -80),
                      "meas_lab": (40, 20, -25), "de": 64.5, "warn": True,
                      "warn_de": 60.0, "colour_range": "purple", "range_k": 3,
                      "range_locs": ["F17", "K23", "V7"], "flag": "",
                      "misfit": misfit}, "both")
    return [t for _sw, t in tile._rows]


def test_the_card_of_knuts_o7(qapp):
    rows = _card(qapp, [{"test": "smaller", "own": (63.9, 64.4),
                         "ref": (75.2, 91.8), "count": 11, "total": 11,
                         "gap": 1.3}])
    i = rows.index("This range has learned, but this")
    assert rows[i + 1:i + 4] == ["one's error is smaller: ΔE 64 here,",
                                 "ΔE 75 to 92 on its confirmed patches",
                                 "(at most ΔE 10 smaller allowed)."]
    assert "one is off in a different way." not in rows


def test_the_card_names_two_reasons_and_says_some(qapp):
    rows = _card(qapp, [
        {"test": "smaller", "own": (49.7, 51.2), "ref": (61.5, 106.0),
         "count": 54, "total": 56, "gap": 0.48},
        {"test": "sideways", "own": (10.3, 15.4), "ref": (0.0, 0.0),
         "count": 9, "total": 56, "gap": 0.29}])
    text = "\n".join(rows)
    assert ("one's error is smaller: ΔE 49.7 to 51.2 here,\n"
            "ΔE 61.5 to 106.0 on some of its confirmed patches") in text
    assert ("Its error also points another way:\nΔE 10.3 to 15.4 sideways\n"
            "(at most ΔE 10 allowed).") in text


def test_the_standout_card(qapp):
    rows = _card(qapp, [{"test": "standout", "own": (50.0, 50.0),
                         "ref": (30.2, 37.9), "count": 3, "total": 3,
                         "gap": 2.1}])
    text = "\n".join(rows)
    assert ("one stands out from its strip more:\nΔE 50 above its strip,\n"
            "ΔE 30 to 38 on its confirmed patches\n"
            "(at most ΔE 10 more allowed).") in text


def test_a_card_without_numbers_keeps_the_old_line(qapp):
    rows = _card(qapp, [])
    assert "one is off in a different way." in rows


def test_the_tab_hands_the_numbers_to_the_card():
    from ui.tabs.tab_measure import TabMeasure
    j = _learned_judge()
    v = _judge(j, "O7", tuple(0.7 * s for s in SHIFT))
    x = TabMeasure._verdict_extra(v)
    assert [m["test"] for m in x["misfit"]] == ["smaller"]
    assert set(x["misfit"][0]) == {"test", "own", "ref", "count", "total", "gap"}


def test_every_new_line_is_in_every_catalogue():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "data" / "i18n"
    names = [n for n in dir(mm) if n.startswith("_CARD_MISFIT")] + ["_CARD_DE_SPAN"]
    assert len(names) == 14
    for f in sorted(root.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for n in names:
            assert getattr(mm, n) in d, (f.name, n)
        assert mm.M_PATCH_COLOUR_RANGE.body in d, f.name
