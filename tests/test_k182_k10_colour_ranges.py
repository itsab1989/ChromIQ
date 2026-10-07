"""#182 k10: a red patch turns yellow only from its own colour range.

The rule, posted in 5961078418 and confirmed by Knut (5961180259) and by
Sebastian: 13 colour ranges (greys split by lightness, then hue sectors),
classified from each patch's EXPECTED colour against the chart's own white
(on an RGB chart from its RGB numbers read as sRGB, Knut 5963411325); a
range learns once three of its patches are confirmed (beta 9, Knut
5979886227: no ΔE 6 spacing any more, and similar patches of other strips
confirm each other, tests/test_k22_peer_confirmation.py); then a red patch of
that range that is off the same way turns yellow.

Each part has a test that fails without it:

* the ranges and their edges:     test_the_thirteen_ranges_and_their_edges
* the chart's white:              test_greys_are_greys_against_the_charts_own_white,
                                  test_the_white_comes_from_the_chart
* the white is sticky:            test_a_reset_never_falls_back_to_d50
* no spacing any more:            test_there_is_no_spacing_count_any_more
* three to learn, only own range: test_a_range_learns_at_three_confirmations,
                                  test_another_range_never_learns_from_this_one
* both directions (rejudge):      test_an_earlier_red_turns_yellow_and_back
* closest, ties by location:      test_the_closest_confirmed_patch_is_named
* the preview flips in place:     test_the_preview_flips_an_earlier_patch_both_ways
* the one reset helper:           test_every_reset_of_the_judge_goes_through_one_helper
* stored learned entries:         test_a_learned_patch_is_stored_like_its_range

Knut 5963411325 ("do the recommended for all three", on 5963152271):

* targen's own estimate:          test_the_estimate_is_targens_own
* an RGB chart, by its RGB:       test_an_rgb_chart_is_classified_by_its_device_rgb,
                                  test_one_device_patch_is_one_range_whatever_its_expected_colour
* the 315 edge:                   test_the_thirteen_ranges_and_their_edges,
                                  test_50_0_100_is_blue
* other charts, per chart:        test_a_chart_without_rgb_keeps_the_expected_colour_rule
* the 0..255 guard:               test_a_chart_on_the_255_scale_is_read_on_100
* a calibrated chart:             test_a_calibrated_chart_reads_its_ti1
* the map is sticky like white:   test_the_device_ranges_survive_a_reset
* the tab, per chart:             test_the_tab_reads_the_ranges_once_per_chart,
                                  test_stored_memories_are_classified_again
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
    (_lch(50, 40, 310.001), "blue"),          # 310 was the edge before 5963411325
    (_lch(50, 40, 314.999), "blue"),
    # Purple/violet (315 to 325) was merged into blue in beta 11 (Knut
    # 5983470377, answer 4); the edge was 315 (5963411325).
    (_lch(50, 40, 315.001), "blue"),
    (_lch(50, 40, 324.999), "blue"),
    (_lch(50, 40, 325.001), "magenta"),
    (_lch(50, 40, 345.001), "pink"),
    ((50.0, 40.0, -1e-15), "pink"),           # -1e-17 % 360 == 360.0
])
def test_the_twelve_ranges_and_their_edges(lab, want):
    assert pf.colour_range_of_lab(lab) == want
    assert len(pf.RANGES) == 12 and want in pf.RANGES
    assert "purple" not in pf.RANGES


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


# ---- k: the confirmations (beta 9: no spacing, Knut 5979886227) -----------------
def test_there_is_no_spacing_count_any_more():
    """The ΔE 6 spacing between a range's three confirmations is gone, with
    its constant and its counter; the count of three stays."""
    assert not hasattr(pf, "spaced_count")
    assert not hasattr(pf, "RANGE_SPACING_DE")
    assert pf.RANGE_CONFIRMATIONS == 3


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


def test_a_range_learns_at_three_confirmations():
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
    # three CLOSE confirmations count as three now (Knut 5979886227: the
    # four magenta patches within ΔE 4.7 must not count as one)
    j2 = pf.FlagJudge()
    for n in range(3):
        _confirm(j2, f"X{n}", (30.0 + n, 20.0, -60.0))
    assert j2.range_status("blue")[0] == 3
    assert j2.judge("P1", probe, _m(probe), 32.4, True).flag == pf.FLAG_LEARNED


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
    magenta = _lch(40, 60, 335)                   # magenta, not blue
    v = j.judge("P1", magenta, _m(magenta), 32.4, True)
    assert v.colour_range == "magenta" and v.flag is pf.FLAG_RED and v.range_k == 0


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
                                   "patch_warn_outlier_fence": False,
                                   # The limit's yellow rule alone: F1 is
                                   # also a neighbour suspect at the default
                                   # buffer, and then only its own re-read
                                   # clears it (Knut, #182 5984174575).
                                   "patch_neighbour_buffer_de": 50.0})
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
    # Off the same way as the blues but half as far again: like them (no upper
    # bound, 5963044182), yet not a similar patch (errors 16 apart, > 10), so
    # it is learned, never confirmed by them (Knut 5979886227).
    LONG = tuple(1.5 * v for v in SHORT)
    tab._on_strip_measured(_event("F", [("F1", probe, _m(probe, LONG))]))
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
    assert "Confirmed: A1, A2, A3" in rows
    # A3 read again, clean: the range has two now, and F1 is red again
    clean = blues[:2] + [("A3", BLUES[2], BLUES[2])]
    tab._on_strip_measured(_event("A", clean))
    assert _flags(tab)["F1"] is True
    info = _info(tab, "F1")
    assert info["flag"] == "" and info["range_k"] == 2
    assert "2 of 3 confirmations so far" in _card(qapp, info)


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
            assert "judge.reset(white=white, device_ranges=device_ranges)" in body
            assert "white=white, device_ranges=device_ranges)" in body
            continue
        if name == "_flag_judge":
            assert resets == [] and "FlagJudge(" in body
            assert "white=white, device_ranges=device_ranges)" in body
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
             mm._CARD_RANGE_CONFIRMED_LEARNED, mm._CARD_PEER_1,
             mm._CARD_PEER_2, mm._CARD_RED_READ_AGAIN, mm._CARD_YELLOW_NO_NEED,
             mm._CARD_MISFIT_SMALLER, mm._CARD_MISFIT_SMALLER_NEXT,
             mm._CARD_MISFIT_SMALLER_LIMIT, mm._CARD_MISFIT_SIDEWAYS,
             mm._CARD_MISFIT_SIDEWAYS_NEXT, mm._CARD_MISFIT_SIDEWAYS_DE,
             mm._CARD_MISFIT_SIDEWAYS_LIMIT, mm._CARD_MISFIT_STANDOUT,
             mm._CARD_MISFIT_STANDOUT_NEXT, mm._CARD_MISFIT_STANDOUT_DE,
             mm._CARD_MISFIT_STANDOUT_LIMIT, mm._CARD_MISFIT_REFS,
             mm._CARD_MISFIT_REFS_SOME, mm._CARD_DE_SPAN,
             mm._CARD_MISFIT_LANDED, mm._CARD_MISFIT_LANDED_DE,
             mm._CARD_RANGE_LANDED_1, mm._CARD_RANGE_LANDED_2,
             mm._CARD_VERIFY_RED_1, mm._CARD_VERIFY_RED_2,
             mm._CARD_VERIFY_RED_3, mm._CARD_VERIFY_SAME_1,
             mm._CARD_VERIFY_SAME_2, mm._CARD_VERIFY_YELLOW_1,
             mm._CARD_VERIFY_YELLOW_2, mm._CARD_VERIFY_YELLOW_3,
             mm._CARD_VERIFY_YELLOW_4, mm._CARD_VERIFY_LEARNED,
             mm._CARD_LATER_PROFILE_1, mm._CARD_LATER_PROFILE_2,
             mm._CARD_LATER_PROFILE_3, mm._CARD_LATER_PROFILE_4,
             mm._CARD_LATER_PROFILE_5, mm._CARD_LATER_PROFILE_6,
             mm._CARD_LATER_PROFILE_SAME_1, mm._CARD_LATER_PROFILE_SAME_2,
             mm._CARD_LATER_PROFILE_YELLOW_1, mm._CARD_LATER_PROFILE_YELLOW_2]
    assert msg.body.split("\n") == lines
    assert msg.title == mm._CARD_RANGE
    for line in lines + [msg.title]:
        assert len(line) <= 44, line
        assert "—" not in line
    assert set(mm.RANGE_NAMES) == set(pf.RANGES)


# ---- Knut 5963411325: an RGB chart's ranges from its RGB numbers, as sRGB -------
DATA = os.path.join(os.path.dirname(__file__), "data")


def _rgb_ti2(path, rows, *, fields="RGB_R RGB_G RGB_B", xyz=None, cal=False,
             white="95.050000 100.000000 108.900000"):
    """A .ti2 with SAMPLE_ID, SAMPLE_LOC, the device *fields* and XYZ.
    *rows*: (loc, device values). The XYZ is deliberately NOT the estimate of
    the device values (a profile's prediction, say): *xyz*, or a green."""
    nf = len(fields.split())
    lines = []
    for n, (loc, dev) in enumerate(rows, 1):
        x = xyz or (20.0, 40.0, 10.0)
        lines.append(f'{n} "{loc}" ' + " ".join(f"{v:.5f}" for v in dev)
                     + " " + " ".join(f"{v:.5f}" for v in x))
    text = ("CTI2\n\n" f'APPROX_WHITE_POINT "{white}"\n'
            f"NUMBER_OF_FIELDS {nf + 5}\nBEGIN_DATA_FORMAT\n"
            f"SAMPLE_ID SAMPLE_LOC {fields} XYZ_X XYZ_Y XYZ_Z\n"
            f"END_DATA_FORMAT\nNUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n"
            + "\n".join(lines) + "\nEND_DATA\n")
    if cal:
        text += ("CAL\n\nDESCRIPTOR \"Argyll Device Calibration State\"\n"
                 "NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
                 "RGB_I RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n"
                 "NUMBER_OF_SETS 2\nBEGIN_DATA\n0 0 0 0\n1 1 1 1\nEND_DATA\n")
    path.write_text(text, encoding="utf-8")
    return path


def _ti1(path, rows):
    lines = [f"{n} " + " ".join(f"{v:.5f}" for v in dev)
             for n, (_loc, dev) in enumerate(rows, 1)]
    path.write_text("CTI1\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
                    "SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n"
                    f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n"
                    + "\n".join(lines) + "\nEND_DATA\n", encoding="utf-8")
    return path


def test_the_estimate_is_targens_own():
    """ArgyllCMS 3.5.0 targen, run with no profile (-d3 -s5 -g5 -f100): its
    XYZ for every patch, and its white, are what the classification reads the
    RGB numbers as (a flat 0.01 flare, the model's own white, not D65)."""
    from workflow import printer_calibration as pc
    fields, rows, kw = pc.read_table(os.path.join(DATA, "targen350_rgb.ti1"))
    assert kw["ORIGINATOR"] == "Argyll targen" and len(rows) == 100
    white = tuple(float(v) / 100 for v in kw["APPROX_WHITE_POINT"].split())
    assert pf.TARGEN_WHITE == pytest.approx(white, abs=1e-6)
    worst = 0.0
    for r in rows.values():
        est = pf.targen_estimate_xyz([float(r[f]) for f in pf.RGB_FIELDS])
        got = [float(r[f]) / 100 for f in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
        worst = max(worst, max(abs(a - b) for a, b in zip(est, got)))
    assert worst < 1e-6, worst


@pytest.mark.parametrize("rgb,want", [
    ((50, 0, 100), "blue"),          # hue 311.3°: purple at the old 310° edge
    ((0, 0, 100), "blue"),           # hue 305.6°
    ((100, 0, 100), "magenta"),      # hue 328.2°
    ((0, 100, 0), "green"),          # hue 136.2°: 130° stays the edge
    ((100, 0, 0), "red"),
    ((100, 100, 0), "yellow"),
    ((0, 100, 100), "cyan"),
    ((0, 0, 0), "grey_dark"),
    ((50, 50, 50), "grey_mid"),
    ((100, 100, 100), "grey_light"),
])
def test_50_0_100_is_blue(rgb, want):
    assert pf.colour_range_of_rgb(rgb) == want


def test_an_rgb_chart_is_classified_by_its_device_rgb(tmp_path):
    """The chart's XYZ says green for every patch (a profile's prediction);
    the ranges follow the RGB numbers, by SAMPLE_LOC, from .ti2 or .ti1 path."""
    rows = [("A1", (50, 0, 100)), ("A2", (0, 100, 0)), ("B1", (50, 50, 50))]
    p = _rgb_ti2(tmp_path / "c.ti2", rows)
    want = {"A1": "blue", "A2": "green", "B1": "grey_mid"}
    assert pf.chart_device_ranges(p) == want
    assert pf.chart_device_ranges(p.with_suffix(".ti1")) == want
    assert pf.chart_device_ranges(tmp_path / "missing.ti2") is None
    assert pf.chart_device_ranges(None) is None


def test_one_device_patch_is_one_range_whatever_its_expected_colour():
    """While the chart's map is set, the expected colour never decides the
    range: a patch is its device range whatever expected colour it carries,
    and a location the chart does not hold has no range (never learns)."""
    j = pf.FlagJudge(white=D65, device_ranges={"P1": "blue", "P2": "blue",
                                               "X1": "blue",
                                               "X2": "blue", "X3": "blue"})
    green, purple = _lch(60, 50, 150), _lch(40, 60, 318)
    for e in (green, purple, BLUES[0]):
        assert j.judge("P1", e, _m(e), 32.4, True).colour_range == "blue"
    v = j.judge("Z9", BLUES[0], _m(BLUES[0]), 32.4, True)
    assert v.colour_range == "" and v.range_k == 0
    for n, e in enumerate(BLUES, 1):
        _confirm(j, f"X{n}", e)
    # a purple expected colour of a device-blue patch learns from the blues
    # (a patch not read before: P1's own earlier purple reading would confirm
    # it instead, since beta 12 compares a re-read with every earlier reading,
    # Knut #182 6045500910)
    assert j.judge("P2", purple, _m(purple), 32.4, True).flag == pf.FLAG_LEARNED
    # the location the chart does not hold stays red, with no range
    _confirm(j, "Z9", BLUES[0])
    assert j.range_status("") == (0, ())
    assert j.judge("Z8", BLUES[1], _m(BLUES[1]), 32.4, True).flag is pf.FLAG_RED


def test_a_chart_without_rgb_keeps_the_expected_colour_rule(tmp_path):
    """Per chart, never per patch: CMYK, N-channel, no device columns, or one
    row that does not parse, and the whole chart keeps today's rule."""
    cmyk = _rgb_ti2(tmp_path / "k.ti2", [("A1", (100, 0, 0, 0))],
                    fields="CMYK_C CMYK_M CMYK_Y CMYK_K")
    assert pf.chart_device_ranges(cmyk) is None
    six = _rgb_ti2(tmp_path / "n.ti2", [("A1", (0, 0, 100, 0, 0, 0))],
                   fields="RGB_R RGB_G RGB_B CMYK_C CMYK_M CMYK_Y")
    assert pf.chart_device_ranges(six) is None
    assert pf.chart_device_ranges(_ti2(tmp_path, "")) is None
    bad = _rgb_ti2(tmp_path / "b.ti2", [("A1", (0, 0, 100)), ("A2", (0, 0, 100))])
    bad.write_text(bad.read_text(encoding="utf-8").replace(
        '2 "A2" 0.00000', '2 "A2" nan'), encoding="utf-8")
    assert pf.chart_device_ranges(bad) is None
    # and the judge with no map is the expected-colour rule, against the white
    j = pf.FlagJudge(white=D65, device_ranges=None)
    assert j.judge("A1", BLUES[0], _m(BLUES[0]), 32.4, True).colour_range == \
        pf.colour_range(BLUES[0], D65)


def test_a_chart_on_the_255_scale_is_read_on_100(tmp_path):
    rows = [("A1", (127.5, 0, 255)), ("A2", (0, 255, 0)), ("A3", (100, 100, 100))]
    got = pf.chart_device_ranges(_rgb_ti2(tmp_path / "c.ti2", rows))
    # 100 100 100 on a 0..255 chart is a mid grey, not white
    assert got == {"A1": "blue", "A2": "green", "A3": "grey_mid"}
    assert pf.colour_range_of_rgb((100, 100, 100)) == "grey_light"


def test_a_calibrated_chart_reads_its_ti1(tmp_path):
    """A layout-engine chart printed with -K before beta 5 holds CALIBRATED
    values in its .ti2: a chart carrying a calibration reads the .ti1's."""
    ti1_rows = [("A1", (50, 0, 100)), ("A2", (0, 0, 0))]
    ti2_rows = [("A1", (80, 0, 70)), ("A2", (0, 0, 0))]      # calibrated
    _ti1(tmp_path / "c.ti1", ti1_rows)
    p = _rgb_ti2(tmp_path / "c.ti2", ti2_rows, cal=True)
    assert pf.colour_range_of_rgb((80, 0, 70)) != "blue"
    assert pf.chart_device_ranges(p)["A1"] == "blue"
    # without a calibration the .ti2 is the chart, whatever the .ti1 says
    q = _rgb_ti2(tmp_path / "c.ti2", ti2_rows, cal=False)
    assert pf.chart_device_ranges(q)["A1"] == pf.colour_range_of_rgb((80, 0, 70))


def test_the_device_ranges_survive_a_reset():
    m = {"A1": "blue"}
    j = pf.FlagJudge(white=D65, device_ranges=m)
    j.reset()
    assert j.device_ranges == m and j.white == D65
    j.reset(white=D65, device_ranges=None)
    assert j.device_ranges is None
    j.set_device_ranges({"A1": "green"})
    assert j.range_of("A1", BLUES[0]) == "green"


def _rgb_tab(tmp_path, rows):
    tab = _small_tab(tmp_path)
    tab._ti1_path = _rgb_ti2(tmp_path / "rgb.ti2", rows,
                             white="96.422000 100.000000 82.521000")
    tab._warn_kind_cache = None
    tab._patch_flag_judge = None
    return tab


def test_the_tab_reads_the_ranges_once_per_chart(qapp, tmp_path):
    """F1's expected colour is a violet (318 deg, blue since beta 11); its RGB numbers are blue, so on an RGB
    chart it learns from the confirmed blues. Another chart (no RGB) clears
    the map and the expected-colour rule is back."""
    rows = [("A1", (0, 0, 100)), ("A2", (10, 0, 100)), ("A3", (20, 0, 100)),
            ("F1", (50, 0, 100))]
    tab = _rgb_tab(tmp_path, rows)
    assert tab._chart_device_ranges()["F1"] == "blue"
    purple = _lch(40, 60, 318)
    tab._on_strip_measured(_event("F", [("F1", purple, _m(purple))]))
    assert _info(tab, "F1")["colour_range"] == "blue"
    blues = [(f"A{i}", e, _m(e)) for i, e in enumerate(BLUES, 1)]
    tab._on_strip_measured(_event("A", blues))
    tab._on_strip_measured(_event("A", blues))    # the re-read: confirmed
    assert _flags(tab)["F1"] == pf.FLAG_LEARNED
    assert "Colour range: blue" in _card(qapp, _info(tab, "F1"))
    # a reset of the memory keeps the chart's map
    tab._reset_flag_judge()
    assert tab._flag_judge().device_ranges["F1"] == "blue"
    # another chart: not RGB, so no map, and the judge starts again
    other = _ti2(tmp_path, 'APPROX_WHITE_POINT "96.422 100 82.521"\n')
    tab._ti1_path = other
    assert tab._chart_device_ranges() is None
    judge = tab._flag_judge()
    assert judge.device_ranges is None and judge.confirmed == []
    # The expected-colour rule again: a magenta expected colour is magenta
    # (the chart's device map would have said blue).
    assert judge.range_of("F1", _lch(40, 60, 335)) == "magenta"


def test_stored_memories_are_classified_again(tmp_path):
    """No schema change: a stored confirmed patch carries its expected colour
    only, and is classified by the chart it is loaded under."""
    stored = {"X1": {"kind": "confirmed", "de": 32.4, "prev_de": 32.0,
                     "exp_lab": list(_lch(40, 60, 335)),
                     "meas_lab": list(_m(_lch(40, 60, 335))),
                     "shift": list(SHORT), "standout": None}}
    old = pf.FlagJudge(white=pf.D50_WHITE)
    old.load(stored)
    assert old.range_status("magenta")[1] == ("X1",)
    new = pf.FlagJudge(white=pf.D50_WHITE, device_ranges={"X1": "blue"})
    new.load(stored)
    assert new.range_status("blue")[1] == ("X1",)
    assert new.range_status("magenta")[1] == ()
