"""Every colour range registers re-read confirmations and learns at three
spaced ones; every card line says why (#182, Knut 5969949735 / 5973177088).

Knut saw "2 of 3 spaced confirmations so far" on three yellow blue patches,
and every magenta card on his 1944-patch run stayed at "1 of 3". Replayed on
his own files (``run4/test.confirmed.json`` and the full project's
``Printer_HP_CLJ5550_i1Pro2_ChromIQ.confirmed.json``) the counts are right by
the approved rule (k10: three confirmed patches pairwise at least ΔE 6 apart):

* run 4, blue: A6, E1, L1 confirmed; A6 and L1 are ΔE 2.85 apart, so the
  largest spaced set is two;
* 1944 patches, magenta: F13, AV17, BA13, BM13 confirmed, all within ΔE 4.7
  of each other (the same corner colour, repeated on the chart), so one.

What was missing is the card saying so: it now lists the confirmed patches.
Knut asked for tests over every colour range and every card message; these
are they.

BETA 9 (Knut 5979886227): "the four magenta patches ... count as one" was the
wrong behaviour. The ΔE 6 spacing is gone, so run 4's blue holds three and
learns, and the four magenta corner patches hold four. The beta-8 card lines
explaining the spacing ("Patches closer than ΔE 6 ...") are gone with it.
"""
from __future__ import annotations

import itertools
import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import patch_flags as PF                     # noqa: E402
from workflow.icc_info import xyz_to_lab                   # noqa: E402

SHIFT = (-6.0, -20.0, 25.0)          # a printer falling short of the colour


def _far(points, spacing=8.0, n=3):
    """n points from *points* pairwise at least *spacing* apart (greedy)."""
    chosen = []
    for p in points:
        if all(PF._norm(PF._sub(p[1], q[1])) >= spacing for q in chosen):
            chosen.append(p)
            if len(chosen) == n:
                return chosen
    return None


def _lab_candidates(rng):
    out = []
    for L in range(20, 95, 5):
        for a in range(-100, 101, 6):
            for b in range(-100, 101, 6):
                lab = (float(L), float(a), float(b))
                if PF.colour_range(lab) == rng:
                    out.append((None, lab))
    return out


def _rgb_candidates(rng):
    out = []
    for r, g, b in itertools.product(range(0, 101, 10), repeat=3):
        rgb = (float(r), float(g), float(b))
        if PF.colour_range_of_rgb(rgb) == rng:
            lab = xyz_to_lab(PF.targen_estimate_xyz(rgb), PF.D50_WHITE)
            out.append((rgb, tuple(lab)))
    return out


def _meas(exp):
    return tuple(e + s for e, s in zip(exp, SHIFT))


def _confirm(judge, loc, exp):
    de = PF._norm(SHIFT)
    first = judge.judge(loc, exp, _meas(exp), de, True)
    assert first.flag is PF.FLAG_RED
    again = judge.judge(loc, exp, _meas(exp), de, True)
    assert again.flag == PF.FLAG_CONFIRMED, "a same-colour re-read must confirm"
    return again


def _learns(judge, pts, rng):
    de = PF._norm(SHIFT)
    for i, (_rgb, exp) in enumerate(pts, 1):
        v = _confirm(judge, f"Z{i}", exp)
        assert v.colour_range == rng
        assert v.range_k == i, f"{rng}: confirmation {i} counted as {v.range_k}"
        assert judge.range_learned(rng) is (i == 3)
    # a fourth flagged patch of the range, off in the same way: learned
    exp4 = tuple((a + b) / 2 for a, b in zip(pts[0][1], pts[1][1]))
    v4 = judge.judge("Z9", exp4, _meas(exp4), de, True)
    assert v4.flag == PF.FLAG_LEARNED and v4.like_loc in {"Z1", "Z2", "Z3"}


@pytest.mark.parametrize("rng", PF.RANGES)
def test_every_range_learns_from_three_spaced_confirmations_by_colour(rng):
    """Charts classified by their expected colour (any non-RGB chart)."""
    pts = _far(_lab_candidates(rng))
    assert pts, f"no colours found for {rng}"
    judge = PF.FlagJudge()
    _learns(judge, pts, rng)


@pytest.mark.parametrize("rng", PF.RANGES)
def test_every_range_learns_from_three_spaced_confirmations_by_device_rgb(rng):
    """RGB charts, classified by their device RGB (Knut's charts)."""
    cands = _rgb_candidates(rng)
    pts = _far(cands, spacing=6.5)
    if pts is None:
        pytest.skip(f"no three spaced RGB colours on a 10 % grid for {rng}")
    ranges = {f"Z{i}": rng for i in range(1, 4)}
    ranges["Z9"] = rng
    judge = PF.FlagJudge(device_ranges=ranges)
    _learns(judge, pts, rng)


def test_each_range_is_reachable_through_device_rgb():
    """Knut asked that EVERY group can learn on his charts: every range but
    the narrow purple one has three spaced 10 %-grid colours, and purple has
    them on a 5 % grid."""
    for rng in PF.RANGES:
        if _far(_rgb_candidates(rng), spacing=6.5) is not None:
            continue
        fine = [((r, g, b), tuple(xyz_to_lab(PF.targen_estimate_xyz((r, g, b)),
                                             PF.D50_WHITE)))
                for r, g, b in itertools.product(range(0, 101, 5), repeat=3)
                if PF.colour_range_of_rgb((r, g, b)) == rng]
        assert _far(fine, spacing=6.5) is not None, rng


def test_close_confirmations_each_count_knuts_run4_blue():
    """Knut's run 4 (#182 5969949735): A6, E1, L1, blue; A6-L1 ΔE 2.85. Beta
    9 (5979886227): all three count, the range learns."""
    exp = {"A6": (35.7, 74.0, -120.7), "E1": (39.5, 76.4, -114.3),
           "L1": (34.3, 73.3, -123.0)}
    judge = PF.FlagJudge(device_ranges={k: "blue" for k in exp})
    for loc, lab in exp.items():
        _confirm(judge, loc, lab)
    k, locs = judge.range_status("blue")
    assert (k, locs) == (3, ("A6", "E1", "L1"))
    assert judge.range_learned("blue")


def test_close_confirmations_each_count_knuts_magenta():
    """Knut's 1944-patch run (5973177088): four magenta confirmations of the
    same corner colour. Beta 8 counted them as one; Knut 5979886227 called
    that wrong, so they count as four (capped at three) and the range learns."""
    exp = {"F13": (61.0, 94.3, -78.5), "AV17": (61.2, 93.6, -78.1),
           "BA13": (58.9, 92.4, -81.9), "BM13": (61.1, 94.0, -78.3)}
    judge = PF.FlagJudge(device_ranges={k: "magenta" for k in exp})
    de = PF._norm(SHIFT)
    for loc, lab in exp.items():
        # the fourth is learned on its first reading (the range has learned),
        # and confirmed by its re-read like the others
        judge.judge(loc, lab, _meas(lab), de, True)
        v = judge.judge(loc, lab, _meas(lab), de, True)
        assert v.flag == PF.FLAG_CONFIRMED, loc
    assert judge.range_status("magenta") == (3, ("F13", "AV17", "BA13", "BM13"))
    assert judge.range_learned("magenta")


# ---- the card: every message ---------------------------------------------------
@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _card(qapp, **info):
    from ui.tiff_preview import _PatchInfoTile
    tile = _PatchInfoTile(None)
    base = {"loc": "A6", "exp_rgb": (0, 0, 255), "meas_rgb": (20, 60, 140),
            "exp_lab": (35.7, 74.0, -120.7), "meas_lab": (30.0, 4.0, -44.0),
            "de": 103.0, "warn": True, "warn_de": 80.0}
    base.update(info)
    tile.set_content(base, "both")
    return [t for _sw, t in tile._rows]


GONE = ["spaced", "Patches closer than ΔE 6 in colour",
        "count as one confirmation, so the", "range needs more different colours.",
        "Re-read and the same"]


@pytest.mark.parametrize("flag, k, locs, peers, expect, absent", [
    # confirmed by a re-read, range not learned
    ("confirmed", 2, ("A6", "E1"), (),
     ["Yellow outline: confirmed by a re-read", "Colour range: blue",
      "2 of 3 confirmations so far", "Confirmed: A6, E1"],
     ["This range has learned.", "similar patches"] + GONE),
    # confirmed by a re-read, learned
    ("confirmed", 3, ("A6", "E1", "L1", "P2"), (),
     ["This range has learned."], ["confirmations so far"] + GONE),
    # confirmed by similar patches (beta 9, Knut 5979886227)
    ("confirmed", 2, ("A6", "E1"), ("E1",),
     ["Yellow outline: confirmed by similar patches",
      "Read alike in other strips: E1",
      "ΔE*ab 103.0 reached the patch error\nlimit (80.0, profiling charts with\nestimated colours).",
      "A real difference this printer and", "Keep it for the profile.",
      "Colour range: blue", "2 of 3 confirmations so far",
      "Confirmed: A6, E1"],
     ["confirmed by a re-read", "the reading before"] + GONE),
    ("confirmed", 3, ("A6", "E1", "L1", "P2"), ("E1", "L1", "P2", "Q9"),
     ["Read alike in other strips: E1, L1, P2…", "This range has learned."],
     ["confirmations so far"] + GONE),
    # learned
    ("learned", 3, ("F17", "K23", "V7", "AE4"), (),
     ["Yellow outline: judged like patch AE4", "Colour range: blue",
      "Confirmed: F17, K23, V7…", "Its range has learned: three patches",
      "of it were confirmed.", "so it is taken as real too."], GONE),
    # red, nothing confirmed in its range yet
    ("", 0, (), (), ["Red outline: a large difference", "Colour range: blue"],
     ["confirmations so far", "Confirmed:"] + GONE),
    # red, one of three
    ("", 1, ("F13",), (),
     ["1 of 3 confirmations so far", "Confirmed: F13"], GONE),
    # red, its range learned, off in another way
    ("", 3, ("A6", "E1", "L1"), (),
     ["This range has learned, but this", "one is off in a different way."],
     ["confirmations so far"] + GONE),
])
def test_every_card_message(qapp, flag, k, locs, peers, expect, absent):
    rows = _card(qapp, flag=flag, colour_range="blue", range_k=k,
                 range_locs=locs, like_loc="AE4", prev_de=103.0,
                 peer_locs=peers)
    text = "\n".join(rows)
    for line in expect:
        assert line in text, f"missing {line!r} in:\n{text}"
    for line in absent:
        assert line not in text, f"unexpected {line!r} in:\n{text}"
