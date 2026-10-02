"""#182 k10: a red patch turns yellow only from its own colour range.

The rule, posted in 5961078418 and confirmed by Knut (5961180259) and by
Sebastian: 13 colour ranges (greys split by lightness, then hue sectors),
classified from each patch's EXPECTED colour against the chart's own white; a
range learns once three of its confirmed patches lie pairwise at least ΔE 6
apart; then a red patch of that range that is off the same way turns yellow.

Each part has a test that fails without it:

* the ranges and their edges:     test_the_thirteen_ranges_and_their_edges
* the chart's white:              test_greys_are_greys_against_the_charts_own_white,
                                  test_the_white_comes_from_the_chart
* the white is sticky:            test_a_reset_never_falls_back_to_d50
* k is exact, not greedy:         test_the_spacing_count_is_exact_not_greedy
* three to learn, only own range: test_a_range_learns_at_three_spaced_confirmations,
                                  test_another_range_never_learns_from_this_one
* both directions (rejudge):      test_an_earlier_red_turns_yellow_and_back
* closest, ties by location:      test_the_closest_confirmed_patch_is_named
* the preview flips in place:     test_the_preview_flips_an_earlier_patch_both_ways
* the one reset helper:           test_every_reset_of_the_judge_goes_through_one_helper
* stored learned entries:         test_a_learned_patch_is_stored_like_its_range
"""
from __future__ import annotations

import inspect
import math
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from workflow import measurement_messages as mm  # noqa: E402
from workflow import patch_flags as pf  # noqa: E402

from tests.test_k182_two_limits_and_the_yellow_outline import (  # noqa: E402
    _card, _flags, _info, _tab)

D65 = (0.9505, 1.0, 1.089)


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def _lch(L, C, h):
    return (L, C * math.cos(math.radians(h)), C * math.sin(math.radians(h)))


# ---- the ranges ---------------------------------------------------------------
@pytest.mark.parametrize("lab,want", [
    ((20.0, 7.99, 0.0), "grey_dark"),
    ((34.99, 0.0, 0.0), "grey_dark"),
    ((35.0, 0.0, 0.0), "grey_mid"),           # 35 is mid grey
    ((69.99, 3.0, -3.0), "grey_mid"),
    ((70.0, 0.0, 0.0), "grey_light"),         # 70 is light grey
    ((50.0, 8.0, 0.0), "pink"),               # chroma 8 is no longer grey
    (_lch(50, 40, 14.999), "pink"),
    (_lch(50, 40, 15.001), "red"),
    (_lch(50, 40, 50.001), "orange"),
    (_lch(50, 40, 75.001), "yellow"),
    (_lch(50, 40, 110.001), "yellow_green"),
    (_lch(50, 40, 130.001), "green"),
    (_lch(50, 40, 165.001), "cyan"),
    (_lch(50, 40, 239.999), "cyan"),
    (_lch(50, 40, 240.001), "blue"),
    (_lch(50, 40, 309.999), "blue"),
    (_lch(50, 40, 310.001), "purple"),        # the approved edge, unchanged
    (_lch(50, 40, 325.001), "magenta"),
    (_lch(50, 40, 345.001), "pink"),
    ((50.0, 40.0, -1e-15), "pink"),           # -1e-17 % 360 == 360.0
])
def test_the_thirteen_ranges_and_their_edges(lab, want):
    assert pf.colour_range_of_lab(lab) == want
    assert len(pf.RANGES) == 13 and want in pf.RANGES


def test_greys_are_greys_against_the_charts_own_white():
    """An RGB chart's grey is D65-neutral (printtarg's sRGB). Read against
    D50, as the tab's L*a*b* is, it looks blue; against the chart's white it
    is the grey it is."""
    from workflow.icc_info import xyz_to_lab
    grey_xyz = tuple(0.2 * w for w in D65)
    lab_d50 = xyz_to_lab(grey_xyz)
    assert math.hypot(lab_d50[1], lab_d50[2]) > 8      # not grey against D50
    assert pf.colour_range(lab_d50) != "grey_mid"
    assert pf.colour_range(lab_d50, D65) == "grey_mid"


def _ti2(tmp_path, white_line):
    p = tmp_path / "c.ti2"
    p.write_text("CTI2\n\n" + white_line + "NUMBER_OF_FIELDS 1\n"
                 "BEGIN_DATA_FORMAT\nSAMPLE_ID\nEND_DATA_FORMAT\n"
                 "NUMBER_OF_SETS 0\nBEGIN_DATA\nEND_DATA\n", encoding="utf-8")
    return p


def test_the_white_comes_from_the_chart(tmp_path):
    p = _ti2(tmp_path, 'APPROX_WHITE_POINT "95.050000 100.000000 108.900000"\n')
    assert pf.chart_white(p) == pytest.approx(D65)
    assert pf.chart_white(p.with_suffix(".ti1")) == pytest.approx(D65)
    for bad in ("", 'APPROX_WHITE_POINT "95.05 100"\n',
                'APPROX_WHITE_POINT "a b c"\n',
                'APPROX_WHITE_POINT "95.05 0 108.9"\n',
                'APPROX_WHITE_POINT "95.05 -1 108.9"\n'):
        assert pf.chart_white(_ti2(tmp_path, bad)) == pf.D50_WHITE, bad
    assert pf.chart_white(tmp_path / "missing.ti2") == pf.D50_WHITE
    assert pf.chart_white(None) == pf.D50_WHITE


def test_a_reset_never_falls_back_to_d50():
    j = pf.FlagJudge(white=D65)
    j.reset()
    assert j.white == D65
    j.reset(white=pf.D50_WHITE)
    assert j.white == pf.D50_WHITE


# ---- k: the spaced confirmations ---------------------------------------------
def test_the_spacing_count_is_exact_not_greedy():
    """A greedy pick in this order takes P first, which is within 6 of both A
    and B, and ends at 2; A, B and C are pairwise at least 6 apart."""
    P, A, B, C = (5, 0, 0), (0, 0, 0), (10, 0, 0), (0, 8, 0)
    assert pf.spaced_count([P, A, B, C]) == 3
    assert pf.spaced_count([P, A]) == 1
    assert pf.spaced_count([A, (6.0, 0, 0)]) == 2       # exactly 6 counts
    assert pf.spaced_count([A, (5.99, 0, 0)]) == 1
    assert pf.spaced_count([]) == 0
    assert pf.spaced_count([A, B, C, (20, 0, 0), (0, 20, 0)]) == 3   # capped


#: Blues (D50, hue about 288°) pairwise ΔE 7 apart, and how each falls short.
BLUES = [(30.0, 20.0, -60.0), (37.0, 20.0, -60.0), (44.0, 20.0, -60.0)]
SHORT = (5.0, -20.0, 25.0)


def _m(e, shift=SHORT):
    return tuple(a + b for a, b in zip(e, shift))


def _confirm(j, loc, e, shift=SHORT, standout=None):
    for _ in range(2):
        v = j.judge(loc, e, _m(e, shift), 32.4, True, standout=standout)
    assert v.flag == pf.FLAG_CONFIRMED
    return v


def test_a_range_learns_at_three_spaced_confirmations():
    j = pf.FlagJudge()
    probe = (33.0, 21.0, -61.0)
    for n, e in enumerate(BLUES, 1):
        v = j.judge(f"P{n}", probe, _m(probe), 32.4, True)
        assert v.colour_range == "blue" and v.range_k == n - 1
        assert v.flag is pf.FLAG_RED, n
        _confirm(j, f"X{n}", e)
    v = j.judge("P9", probe, _m(probe), 32.4, True)
    assert v.flag == pf.FLAG_LEARNED and v.range_k == 3
    assert v.range_locs == ("X1", "X2", "X3")
    # three CLOSE confirmations are not three spaced ones
    j2 = pf.FlagJudge()
    for n in range(3):
        _confirm(j2, f"X{n}", (30.0 + n, 20.0, -60.0))
    assert j2.range_status("blue")[0] == 1
    assert j2.judge("P1", probe, _m(probe), 32.4, True).flag is pf.FLAG_RED


def test_a_learned_patch_never_counts_and_a_confirmed_one_stays_yellow():
    j = pf.FlagJudge()
    v = _confirm(j, "X1", BLUES[0])
    assert v.range_k == 1                         # confirmed, range not learned
    for e, loc in ((BLUES[1], "X2"), (BLUES[2], "X3")):
        _confirm(j, loc, e)
    for n, e in enumerate([(51.0, 20.0, -60.0), (58.0, 20.0, -60.0)]):
        assert j.judge(f"L{n}", e, _m(e), 32.4, True).flag == pf.FLAG_LEARNED
    assert j.confirmed == ["X1", "X2", "X3"]
    assert j.range_status("blue") == (3, ("X1", "X2", "X3"))


def test_another_range_never_learns_from_this_one():
    j = pf.FlagJudge()
    for n, e in enumerate(BLUES, 1):
        _confirm(j, f"X{n}", e)
    purple = _lch(40, 60, 318)                    # purple, ΔE ~26 from X1
    v = j.judge("P1", purple, _m(purple), 32.4, True)
    assert v.colour_range == "purple" and v.flag is pf.FLAG_RED and v.range_k == 0


def test_an_earlier_red_turns_yellow_and_back():
    """R3: judged before the range learned, re-judged after; and a confirmed
    patch read clean drops out, so the range un-learns and it is red again."""
    j = pf.FlagJudge()
    probe = (33.0, 21.0, -61.0)
    assert j.judge("P1", probe, _m(probe), 32.4, True).flag is pf.FLAG_RED
    for n, e in enumerate(BLUES, 1):
        _confirm(j, f"X{n}", e)
    changed = j.rejudge()
    assert changed["P1"].flag == pf.FLAG_LEARNED
    assert changed["P1"].like_loc in ("X1", "X2")
    assert j.rejudge() == {}                      # nothing changes twice
    j.judge("X3", BLUES[2], BLUES[2], 0.0, False)  # X3 read clean
    changed = j.rejudge()
    assert changed["P1"].flag is pf.FLAG_RED and changed["P1"].range_k == 2
    # and the confirmed ones are told the new count too, still yellow
    assert changed["X1"].flag == pf.FLAG_CONFIRMED and changed["X1"].range_k == 2
    assert "X3" not in changed                    # no outline at all now


def test_the_closest_confirmed_patch_is_named():
    """By expected colour (ΔE*ab, D50); ties by location, A9 before A10."""
    j = pf.FlagJudge()
    _confirm(j, "A10", (37.0, 20.0, -60.0))
    _confirm(j, "A9", (37.0, 20.0, -60.0))
    _confirm(j, "B1", (30.0, 20.0, -60.0))
    _confirm(j, "B2", (44.0, 20.0, -60.0))
    near = (36.0, 20.0, -60.0)
    v = j.judge("P", near, _m(near), 32.4, True)
    assert v.flag == pf.FLAG_LEARNED and v.like_loc == "A9"
    near_b1 = (31.0, 20.0, -60.0)
    assert j.judge("Q", near_b1, _m(near_b1), 32.4, True).like_loc == "B1"
    assert v.range_locs == ("A9", "A10", "B1", "B2")


def test_a_learned_patch_is_stored_like_its_range():
    j = pf.FlagJudge()
    for n, e in enumerate(BLUES, 1):
        _confirm(j, f"X{n}", e)
    probe = (33.0, 21.0, -61.0)
    j.judge("P1", probe, _m(probe), 32.4, True)
    out = j.export()
    assert out["P1"] == {"kind": "learned", "like": "X1"}
    # loaded back: the confirmed ones are references, the learned one is not
    k = pf.FlagJudge(white=D65)
    assert k.load(out) == 3 and k.confirmed == ["X1", "X2", "X3"]
    assert k.white == D65


# ---- the tab and the preview ---------------------------------------------------
def _xyz100(lab):
    return [v * 100.0 for v in pf._lab_d50_to_xyz(lab)]


def _event(letter, rows):
    """A strip_read event: rows of (loc, expected D50 Lab, measured D50 Lab)."""
    out = []
    for loc, e, m in rows:
        out.append({"id": loc, "loc": loc, "exyz": _xyz100(e),
                    "xyz": _xyz100(m),
                    "de": round(math.dist(e, m), 2)})
    return {"strip": letter, "patches": out}


def _small_tab(tmp_path):
    from tests.test_k182_two_limits_and_the_yellow_outline import KNUT  # noqa: F401
    tab = _tab(tmp_path, settings={"chartread_engine": "chromiq",
                                   pf.ESTIMATED_KEY: 20.0,
                                   "patch_warn_outlier_fence": False})
    # A grey-neutral D50 chart: the ranges are classified against D50 here.
    tab._ti1_path.write_text(
        tab._ti1_path.read_text(encoding="utf-8").replace(
            "95.050000 100.000000 108.900000", "96.422000 100.000000 82.521000"),
        encoding="utf-8")
    tab._warn_kind_cache = None
    tab._patch_flag_judge = None
    return tab


def test_the_preview_flips_an_earlier_patch_both_ways(qapp, tmp_path):
    tab = _small_tab(tmp_path)
    probe = (33.0, 21.0, -61.0)
    tab._on_strip_measured(_event("F", [("F1", probe, _m(probe))]))
    assert _flags(tab)["F1"] is True
    blues = [(f"A{i}", e, _m(e)) for i, e in enumerate(BLUES, 1)]
    tab._on_strip_measured(_event("A", blues))
    assert _flags(tab)["F1"] is True and _info(tab, "F1")["range_k"] == 0
    tab._on_strip_measured(_event("A", blues))    # the re-read: all confirmed
    flags = _flags(tab)
    assert [flags[f"A{i}"] for i in (1, 2, 3)] == [pf.FLAG_CONFIRMED] * 3
    assert flags["F1"] == pf.FLAG_LEARNED         # the EARLIER patch flipped
    info = _info(tab, "F1")
    assert info["flag"] == "learned" and info["range_k"] == 3
    rows = _card(qapp, info)
    assert f"Yellow outline: judged like patch {info['like_loc']}" in rows
    assert "Colour range: blue" in rows
    assert "Re-read and the same: A1, A2, A3" in rows
    # A3 read again, clean: the range has two now, and F1 is red again
    clean = blues[:2] + [("A3", BLUES[2], BLUES[2])]
    tab._on_strip_measured(_event("A", clean))
    assert _flags(tab)["F1"] is True
    info = _info(tab, "F1")
    assert info["flag"] == "" and info["range_k"] == 2
    assert "2 of 3 spaced confirmations so far" in _card(qapp, info)


def test_update_patch_flags_changes_only_the_named_patches(qapp, tmp_path):
    from PyQt6.QtGui import QColor
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    a, b = QRect(0, 0, 10, 10), QRect(20, 0, 10, 10)
    c = QColor("#3050ff")
    p.set_patch_overlay(0, [(a, c, c, True), (b, c, c, True)])
    p.set_patch_info(0, [(a, {"loc": "A1", "flag": ""}),
                         (b, {"loc": "A2", "flag": ""})])
    p.update_patch_flags(0, {QRect(0, 0, 10, 10): (pf.FLAG_LEARNED,
                                                   {"flag": "learned"})})
    assert [it[3] for it in p._patch_overlay[0]] == [pf.FLAG_LEARNED, True]
    assert [d["flag"] for _b, d in p._patch_info[0]] == ["learned", ""]
    p.update_patch_flags(3, {a: (True, {})})       # no such page: nothing
    assert 3 not in p._patch_overlay


def test_every_reset_of_the_judge_goes_through_one_helper():
    """R0: the judge is made and reset with the chart's white, in ONE place,
    so no path can leave the colour ranges on D50 by forgetting it."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    methods = re.split(r"\n    def ", src)
    for body in methods:
        name = body.split("(", 1)[0]
        resets = re.findall(r"judge(?:\(\))?\.reset\(", body)
        makes = re.findall(r"FlagJudge\(", body)
        if name == "_reset_flag_judge":
            assert "judge.reset(white=white)" in body
            assert "FlagJudge(white=white)" in body
            continue
        if name == "_flag_judge":
            assert resets == [] and "FlagJudge(white=white)" in body
            continue
        assert not resets, f"{name} resets the judge itself"
        assert not makes, f"{name} makes a judge itself"


def test_the_card_lines_are_the_proposed_messages():
    """M-PATCH-COLOUR-RANGE (§M-PROPOSED): every line the card can show is in
    the message, and each fits the card's hand-broken width."""
    msg = mm.CATALOGUE["M-PATCH-COLOUR-RANGE"]
    assert not msg.approved
    lines = [mm._CARD_RANGE_SO_FAR, mm._CARD_RANGE_SAME,
             mm._CARD_RANGE_LEARNED_1, mm._CARD_RANGE_LEARNED_2,
             mm._CARD_RANGE_LEARNED_3, mm._CARD_RANGE_LEARNED_4,
             mm._CARD_RANGE_RED_LEARNED_1, mm._CARD_RANGE_RED_LEARNED_2,
             mm._CARD_RANGE_CONFIRMED_LEARNED]
    assert msg.body.split("\n") == lines
    assert msg.title == mm._CARD_RANGE
    for line in lines + [msg.title]:
        assert len(line) <= 38, line
        assert "—" not in line
    assert set(mm.RANGE_NAMES) == set(pf.RANGES)
