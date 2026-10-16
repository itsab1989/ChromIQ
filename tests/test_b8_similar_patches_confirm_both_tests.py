"""Two tests, one outline: similar patches confirm EACH test (#182, 4.3.5 b8).

Knut, #182 6196599132: *"I confirm all the cases and approve the solution
you recommend"*, to the draft "two tests, one outline" (6188067361) and its
recommended rule: another patch confirms this one when the two ERRORS (the
arrows from expected to measured colour) are within the Same-reading
tolerance, the two were read in DIFFERENT strips, they are in the same colour
range and their expected colours lie within the Colour-neighbour radius. The
same rule for the patch error limit (PE) and the neighbour check (NB). Then
Knut's combination (6181524471): any test red, red; otherwise any yellow,
yellow; otherwise a corrected test, green; a test that is not triggered does
not count.

Every row of the draft's table 4.5 is a test below (``test_row_NN``), at the
judge (the outline and what each test says) and on the card (which approved
or proposed sentences it carries). The case list the independent verifier
works from is ``~/Desktop/ChromIQ-work/2026-10-15_b8_simrule/CASES.md``.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from workflow import measurement_messages as M  # noqa: E402
from workflow import patch_flags as pf  # noqa: E402

BLUE = (33.0, 21.0, -61.0)
SHIFT = (5.0, -20.0, 25.0)              # ΔE*ab 32.4, a printer falling short
LIMIT = 20.0
LOCS = [f"{c}{n}" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for n in range(1, 31)]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _judge(**kw):
    """Every location in ONE colour range (blue), so the range never decides
    unless a test says otherwise; the default radius 15 and tolerance 3."""
    kw.setdefault("device_ranges", {loc: "blue" for loc in LOCS})
    return pf.FlagJudge(**kw)


def _read(j, loc, exp=BLUE, shift=SHIFT, *, pe=True, nb=False, live=True,
          strip=None):
    """One reading of *loc*. *pe*: the patch error limit flags it; *nb*: the
    neighbour check suspects it (the tab's two inputs)."""
    meas = _add(exp, shift)
    return j.judge(loc, exp, meas, pf._norm(shift), pe or nb,
                   strip=strip or loc.rstrip("0123456789"), live=live,
                   reread_only=nb, warn=pe, limit=LIMIT)


def _settle(j):
    """The tab asks rejudge() after every batch."""
    j.rejudge()
    return j._verdicts


def _colour(v) -> str:
    f = v.flag
    if f is True:
        return "red"
    if f is False:
        return "none"
    return {pf.FLAG_CONFIRMED: "yellow", pf.FLAG_LEARNED: "yellow",
            pf.FLAG_CORRECTED: "green"}[f]


# ---- the card ------------------------------------------------------------------
def _card(qapp, loc, v, *, pe, nb, de=None, kind="estimated"):
    """The hover card the tab builds for verdict *v* (``_verdict_extra``
    plus what the tab adds: the limit's flag and the neighbour finding)."""
    from ui.tabs.tab_measure import TabMeasure
    from ui.tiff_preview import _PatchInfoTile
    info = {"loc": loc, "exp_rgb": (0, 0, 255), "meas_rgb": (0, 0, 200),
            "exp_lab": BLUE, "meas_lab": _add(BLUE, SHIFT),
            "de": pf._norm(SHIFT) if de is None else de,
            "warn": bool(pe), "warn_de": LIMIT, "fenced": False,
            "kind": kind, "accurate": False,
            "neighbour": ({"n": 4, "locs": ["X1", "X2", "X3", "X4"],
                           "further": 7.5, "limit": 5.0} if nb else None),
            "nb_compare": None, "nb_detail": None, "pbp": False}
    info.update(TabMeasure._verdict_extra(v))
    host = QWidget()
    tile = _PatchInfoTile(host)
    tile.set_content(info, "both")
    lines = [str(t) for _s, t in tile._rows]
    return " ".join(" ".join(x for x in lines if x).split()), lines


def _n2_once(text, loc):
    """Rows 12, 21 and 22: N2 without its first sentence, because the red
    ending asks for the re-read itself, so the card says it once (Basti,
    2026-10-16, item 10 of the beta 8 review)."""
    assert M._CARDS_NB_REREAD_OTHERS in text
    assert M._CARDS_NB_REREAD.format(loc=loc) not in text
    assert text.count(M._CARD_RED_READ_AGAIN.format(loc=loc)) == 1


def _ab(v):
    return f"ΔE*ab {float(v):.2f}"


def _nb_fmt(text, loc):
    return text.format(d=_ab(7.5), n=4, limit=_ab(5.0),
                       kind=M._CARD_KIND_ESTIMATED, loc=loc)


def _limit_yellow(loc):
    return M._CARDP_LIMIT_YELLOW.format(de=_ab(pf._norm(SHIFT)),
                                        limit=_ab(LIMIT),
                                        kind=M._CARD_KIND_ESTIMATED, loc=loc)


def _limit_red(loc):
    return M._CARDP_LIMIT.format(de=_ab(pf._norm(SHIFT)), limit=_ab(LIMIT),
                                 kind=M._CARD_KIND_ESTIMATED, loc=loc)


#: Three re-read confirmations of the blue range, expected far (ΔE > 15)
#: from BLUE and from each other, so they are nobody's similar patch: the
#: range learns, and a patch off like them is judged like them.
REFS = {"R1": (70.0, 21.0, -61.0), "S1": (33.0, 60.0, -61.0),
        "T1": (33.0, 21.0, -20.0)}


def _learned(j):
    for loc, exp in REFS.items():
        _read(j, loc, exp)
        _read(j, loc, exp)                    # re-read: the same
    assert j.range_learned("blue")


# ---- the rule's conditions ----------------------------------------------------
def test_different_strips_same_range_near_colour_errors_alike():
    j = _judge()
    _read(j, "A1")
    v = _read(j, "B1", _add(BLUE, (5.0, 5.0, 5.0)), _add(SHIFT, (1.0, 1.0, 1.0)))
    assert v.flag == pf.FLAG_CONFIRMED and v.peer_locs == ("A1",)
    assert v.pe_state == pf.STATE_PEER and v.prev_de is None


def test_one_strip_never_confirms_itself():
    j = _judge()
    _read(j, "A1")
    assert _read(j, "A2").flag is pf.FLAG_RED
    _read(j, "C1", nb=True, pe=False)
    assert _read(j, "C2", nb=True, pe=False).flag is pf.FLAG_RED


def test_another_colour_range_never_confirms():
    ranges = {loc: "blue" for loc in LOCS}
    ranges["B1"] = "cyan"
    j = _judge(device_ranges=ranges)
    _read(j, "A1")
    assert _read(j, "B1").flag is pf.FLAG_RED


@pytest.mark.parametrize("radius, d_exp, peers", [
    (15.0, 15.0, True), (15.0, 15.01, False),
    (30.0, 30.0, True), (30.0, 30.01, False)])
def test_the_colour_neighbour_radius_is_the_edge(radius, d_exp, peers):
    j = _judge(peer_radius=radius)
    _read(j, "A1")
    v = _read(j, "B1", _add(BLUE, (d_exp, 0.0, 0.0)))
    assert (v.flag == pf.FLAG_CONFIRMED) is peers


@pytest.mark.parametrize("tol, d_err, peers", [
    (3.0, 3.0, True), (3.0, 3.01, False), (5.0, 5.0, True), (5.0, 5.01, False)])
def test_the_errors_agree_within_the_same_reading_tolerance(tol, d_err, peers):
    j = _judge(same_reading_de=tol)
    _read(j, "A1")
    v = _read(j, "B1", BLUE, _add(SHIFT, (0.0, 0.0, d_err)))
    assert (v.flag == pf.FLAG_CONFIRMED) is peers


def test_the_error_is_compared_not_its_size():
    """Two patches equally far off, one too green and one too red: the same
    ΔE, errors 30 apart. Not similar (the reason for the rule, 6188066945)."""
    j = _judge()
    _read(j, "A1", BLUE, (0.0, -15.0, 0.0))
    v = _read(j, "B1", BLUE, (0.0, 15.0, 0.0))
    assert v.flag is pf.FLAG_RED


def test_changing_the_radius_or_the_tolerance_judges_again():
    j = _judge()
    _read(j, "A1")
    _read(j, "B1", _add(BLUE, (20.0, 0.0, 0.0)))
    assert _settle(j)["B1"].flag is pf.FLAG_RED
    j.set_peer_radius(30.0)
    assert _settle(j)["B1"].flag == pf.FLAG_CONFIRMED
    j.set_peer_radius(15.0)
    assert _settle(j)["B1"].flag is pf.FLAG_RED


def test_a_neighbour_check_red_patch_never_confirms_the_patch_error():
    """4.1 point 6: Q's reading is in doubt, so it confirms nobody's patch
    error (P stays red), while P (not in doubt) confirms Q's part."""
    j = _judge()
    _read(j, "A1", pe=True, nb=True)               # in doubt by NB
    v = _read(j, "B1")
    assert v.flag is pf.FLAG_RED and v.peer_locs == ()
    w = _settle(j)["A1"]
    assert w.flag is pf.FLAG_RED and w.peer_locs == ("B1",)
    assert (w.pe_state, w.nb_state) == (pf.STATE_PEER, pf.STATE_RED)


def test_readings_that_disagree_are_nobodys_similar_patch():
    j = _judge()
    _read(j, "A1")
    _read(j, "A1", BLUE, _add(SHIFT, (0.0, 10.0, 0.0)))   # unsettled
    assert j._verdicts["A1"].unsettled
    assert _read(j, "B1").flag is pf.FLAG_RED


def test_a_learned_patch_never_confirms_anything():
    j = _judge()
    _learned(j)
    far = _add(BLUE, (0.0, 0.0, 20.0))
    long = tuple(1.2 * s for s in SHIFT)
    lv = _read(j, "L1", far, long)
    assert lv.flag == pf.FLAG_LEARNED
    # a red patch near L1 off like it: L1's raw reading makes them
    # similar patches; it is the READING that confirms, never a verdict
    v = _read(j, "M1", _add(far, (1.0, 0.0, 0.0)), long)
    assert v.peer_locs == ("L1",)
    w = _settle(j)["L1"]
    assert w.flag == pf.FLAG_CONFIRMED and w.peer_locs == ("M1",)


# ---- teaching the colour range (Knut 6191537939: "Keep as today") --------------
def test_similar_patches_still_teach_their_range():
    j = _judge()
    _read(j, "A1")
    _read(j, "B1", _add(BLUE, (2.0, 0.0, 0.0)))
    _read(j, "C1", _add(BLUE, (4.0, 0.0, 0.0)))
    _settle(j)
    assert j.range_status("blue") == (3, ("A1", "B1", "C1"))


def test_a_patch_error_confirmed_by_similar_patches_teaches_whatever_nb_says():
    """6188067361, 4.2: the range counts "re-reads or PE similar patches".
    A1's patch error is confirmed by B1 (its outline is red for the
    neighbour check); B1's is not confirmed by A1, whose reading the
    neighbour check holds in doubt (4.1 point 6)."""
    j = _judge()
    _read(j, "A1", pe=True, nb=True)
    _read(j, "B1")
    _settle(j)
    assert j.range_status("blue") == (1, ("A1",))


def test_neighbour_check_similar_patches_alone_teach_nothing():
    j = _judge()
    _read(j, "A1", pe=False, nb=True)
    _read(j, "B1", pe=False, nb=True)
    _settle(j)
    assert j.range_status("blue") == (0, ())


# ---- table 4.5, every row ----------------------------------------------------------
def test_row_01_neither_test(qapp):
    j = _judge()
    v = _read(j, "A1", pe=False, nb=False)
    assert v.flag is pf.FLAG_NONE
    text, _ = _card(qapp, "A1", v, pe=False, nb=False)
    assert "outline" not in text


def test_row_02_pe_red(qapp):
    j = _judge()
    v = _read(j, "A1")
    assert v.flag is pf.FLAG_RED and (v.pe_state, v.nb_state) == ("red", "")
    text, lines = _card(qapp, "A1", v, pe=True, nb=False)
    assert M._CARDP_LIMIT_HEAD in lines and _limit_red("A1") in text
    assert M._CARD_RED_READ_AGAIN.format(loc="A1") in text
    assert M._CARD_PEER_1 not in lines


def test_row_02_the_range_line_reads_as_the_ranges_count(qapp):
    """N6 (Knut 6191537939, approved): C27's red card said "Confirmed: A1,
    A22" and was read as C27 being confirmed by them."""
    j = _judge()
    _read(j, "A1", _add(BLUE, (0, 40, 0)))
    _read(j, "A1", _add(BLUE, (0, 40, 0)))      # re-read: confirmed
    v = _read(j, "C27", _add(BLUE, (0, 0, 40)), (0.0, 25.0, 0.0))
    assert v.flag is pf.FLAG_RED and v.range_locs == ("A1",)
    text, _ = _card(qapp, "C27", v, pe=True, nb=False)
    assert "Patches of this range confirmed so far: A1." in text
    assert "Confirmed: A1" not in text


def test_row_03_pe_readings_disagree(qapp):
    j = _judge()
    _read(j, "A1")
    v = _read(j, "A1", BLUE, _add(SHIFT, (0.0, 10.0, 0.0)))
    assert v.flag is pf.FLAG_RED and v.unsettled
    text, lines = _card(qapp, "A1", v, pe=True, nb=False)
    assert M._CARD_UNSETTLED_HEAD in lines


def test_row_04_pe_reread(qapp):
    j = _judge()
    _read(j, "A1")
    v = _read(j, "A1")
    assert v.flag == pf.FLAG_CONFIRMED and v.pe_state == "reread"
    text, lines = _card(qapp, "A1", v, pe=True, nb=False)
    assert "Yellow outline: confirmed by a re-read" in lines
    assert _limit_yellow("A1") in text
    assert M._CARD_YELLOW_NO_NEED.format(loc="A1") in text


@pytest.mark.parametrize("n_peers", [1, 2])
def test_row_05_pe_similar_patches(qapp, n_peers):
    j = _judge()
    _read(j, "A1")
    for loc in ("B1", "C1")[:n_peers]:
        _read(j, loc, _add(BLUE, (2.0, 0.0, 0.0)))
    v = _settle(j)["A1"]
    assert v.flag == pf.FLAG_CONFIRMED and v.pe_state == "peer"
    text, lines = _card(qapp, "A1", v, pe=True, nb=False)
    assert M._CARD_PEER_1 in lines
    want = (M._CARD_PEER_2_ONE.format(locs="B1") if n_peers == 1
            else M._CARD_PEER_2.format(locs="B1, C1"))
    assert want in text and _limit_yellow("A1") in text
    assert M._CARD_YELLOW_NO_NEED.format(loc="A1") in text
    assert "Read alike in other strips" not in text


def test_row_06_pe_learned(qapp):
    j = _judge()
    _learned(j)
    v = _read(j, "A1", BLUE, tuple(1.2 * s for s in SHIFT))
    assert v.flag == pf.FLAG_LEARNED and v.pe_state == "learned" and v.like_loc
    text, lines = _card(qapp, "A1", v, pe=True, nb=False)
    assert M._CARD_RANGE_LEARNED_1 in lines


def test_row_07_pe_corrected(qapp):
    j = _judge()
    _read(j, "A1")
    v = _read(j, "A1", BLUE, (0.5, 0.5, 0.5), pe=False)
    assert v.flag == pf.FLAG_CORRECTED and v.corrected_by == "limit"
    text, lines = _card(qapp, "A1", v, pe=False, nb=False)
    assert M._CARD_GREEN_HEAD in lines


def test_row_08_nb_red(qapp):
    j = _judge()
    v = _read(j, "A1", pe=False, nb=True)
    assert v.flag is pf.FLAG_RED and (v.pe_state, v.nb_state) == ("", "red")
    text, lines = _card(qapp, "A1", v, pe=False, nb=True)
    assert _nb_fmt(M._CARDP_NB_RED, "A1") in text
    assert M._CARDS_NB_REREAD.format(loc="A1") in text      # row 8: whole
    assert "Only its own re-read" not in text


def test_row_09_nb_reread(qapp):
    j = _judge()
    _read(j, "A1", pe=False, nb=True)
    v = _read(j, "A1", pe=False, nb=True)
    assert v.flag == pf.FLAG_CONFIRMED and v.nb_state == "reread"
    text, lines = _card(qapp, "A1", v, pe=False, nb=True)
    assert "Yellow outline: confirmed by a re-read" in lines
    assert _nb_fmt(M._CARDP_NB_YELLOW, "A1") in text


@pytest.mark.parametrize("n_peers", [1, 2])
def test_row_10_nb_similar_patches(qapp, n_peers):
    j = _judge()
    _read(j, "A1", pe=False, nb=True)
    for loc in ("B1", "C1")[:n_peers]:
        _read(j, loc, pe=False, nb=True)
    v = _settle(j)["A1"]
    assert v.flag == pf.FLAG_CONFIRMED and v.nb_state == "peer"
    text, lines = _card(qapp, "A1", v, pe=False, nb=True)
    assert M._CARD_PEER_1 in lines
    want = (M._CARDS_NB_PEER_ONE.format(locs="B1") if n_peers == 1
            else M._CARDS_NB_PEER.format(locs="B1, C1"))
    assert want in text and _nb_fmt(M._CARDP_NB_YELLOW, "A1") in text
    assert M._CARD_YELLOW_NO_NEED.format(loc="A1") in text


def test_row_11_nb_corrected(qapp):
    j = _judge()
    _read(j, "A1", pe=False, nb=True)
    v = _read(j, "A1", pe=False, nb=False)
    assert v.flag == pf.FLAG_CORRECTED and v.corrected_by == "neighbour"
    text, lines = _card(qapp, "A1", v, pe=False, nb=False)
    assert M._CARD_GREEN_HEAD in lines


def test_row_12_both_red(qapp):
    j = _judge()
    v = _read(j, "A1", nb=True)
    assert v.flag is pf.FLAG_RED and (v.pe_state, v.nb_state) == ("red", "red")
    text, lines = _card(qapp, "A1", v, pe=True, nb=True)
    assert M._CARDP_LIMIT_HEAD in lines and _limit_red("A1") in text
    assert _nb_fmt(M._CARDP_NB_ALSO, "A1") in text
    _n2_once(text, "A1")


def test_row_13_pe_red_nb_similar(qapp):
    j = _judge()
    _read(j, "A1", nb=True)
    _read(j, "B1", pe=False, nb=True)        # off alike, NB only
    v = _settle(j)["A1"]
    assert v.flag is pf.FLAG_RED
    assert (v.pe_state, v.nb_state) == ("red", "peer")
    assert v.nb_peer_locs == ("B1",)
    text, lines = _card(qapp, "A1", v, pe=True, nb=True)
    assert _limit_red("A1") in text
    assert M._CARDS_NB_PEER_PE_RED.format(loc="A1", locs="B1") in text
    assert _nb_fmt(M._CARDP_NB_ALSO, "A1") not in text


def test_row_14_pe_red_nb_corrected(qapp):
    j = _judge()
    _read(j, "A1", BLUE, (2.0, -5.0, 6.0), pe=False, nb=True)
    v = _read(j, "A1", pe=True, nb=False)
    assert v.flag is pf.FLAG_RED and (v.pe_state, v.nb_state) == ("red", "")
    text, lines = _card(qapp, "A1", v, pe=True, nb=False)
    assert M._CARDP_LIMIT_HEAD in lines and M._CARD_GREEN_HEAD not in lines


def test_row_15_pe_disagree_nb_red(qapp):
    j = _judge()
    _read(j, "A1", nb=True)
    v = _read(j, "A1", BLUE, _add(SHIFT, (0.0, 10.0, 0.0)), nb=True)
    assert v.flag is pf.FLAG_RED and v.unsettled and v.nb_state == "red"
    text, lines = _card(qapp, "A1", v, pe=True, nb=True)
    assert M._CARD_UNSETTLED_HEAD in lines
    assert _nb_fmt(M._CARDP_NB_ALSO, "A1") in text


def test_row_16_pe_disagree_nb_corrected():
    j = _judge()
    _read(j, "A1", nb=True)
    v = _read(j, "A1", BLUE, _add(SHIFT, (0.0, 10.0, 0.0)), nb=False)
    assert v.flag is pf.FLAG_RED and v.unsettled and v.nb_state == ""


def test_row_17_disagreeing_readings_are_never_confirmed_by_similar_patches():
    """Impossible combination: an unsettled patch's neighbour check is never
    confirmed by similar patches, however alike they are."""
    j = _judge()
    _read(j, "A1", nb=True)
    _read(j, "A1", BLUE, _add(SHIFT, (0.0, 10.0, 0.0)), nb=True)
    _read(j, "B1", BLUE, _add(SHIFT, (0.0, 10.0, 0.0)), pe=False, nb=True)
    v = _settle(j)["A1"]
    assert v.flag is pf.FLAG_RED and v.unsettled
    assert v.nb_peer_locs == () and v.peer_locs == ()


def test_row_18_both_reread(qapp):
    j = _judge()
    _read(j, "A1", nb=True)
    v = _read(j, "A1", nb=True)
    assert v.flag == pf.FLAG_CONFIRMED
    assert (v.pe_state, v.nb_state) == ("reread", "reread")
    text, lines = _card(qapp, "A1", v, pe=True, nb=True)
    # N5: both sentences, the limit's first
    a, b = _limit_yellow("A1"), _nb_fmt(M._CARDP_NB_YELLOW, "A1")
    assert a in text and b in text and text.index(a) < text.index(b)


def test_rows_19_20_one_reread_confirms_both_tests():
    """Impossible combinations: a re-read is ONE reading; whatever similar
    patches or the range say, a re-read-confirmed patch is Y-re for both."""
    j = _judge()
    _read(j, "B1", pe=False, nb=True)                  # a would-be NB peer
    _read(j, "A1", nb=True)
    v = _read(j, "A1", nb=True)
    v = _settle(j)["A1"]
    assert (v.pe_state, v.nb_state) == ("reread", "reread")


def test_row_21_pe_similar_nb_red(qapp):
    j = _judge()
    _read(j, "A1", nb=True)
    _read(j, "B1")                                    # PE only, alike
    v = _settle(j)["A1"]
    assert v.flag is pf.FLAG_RED
    assert (v.pe_state, v.nb_state) == ("peer", "red")
    text, lines = _card(qapp, "A1", v, pe=True, nb=True)
    assert M._CARDP_LIMIT_HEAD in lines
    assert M._CARDS_PE_PEER_NB_RED_ONE.format(locs="B1", loc="A1") in text
    assert _nb_fmt(M._CARDP_NB_ALSO, "A1") in text
    _n2_once(text, "A1")
    assert _limit_red("A1") not in text


def test_row_22_pe_learned_nb_red(qapp):
    j = _judge()
    _learned(j)
    v = _read(j, "A1", BLUE, tuple(1.2 * s for s in SHIFT), nb=True)
    assert v.flag is pf.FLAG_RED
    assert (v.pe_state, v.nb_state) == ("learned", "red") and v.like_loc
    text, _ = _card(qapp, "A1", v, pe=True, nb=True)
    assert M._CARDS_PE_LEARNED_NB_RED.format(loc="A1", like=v.like_loc) in text
    assert _nb_fmt(M._CARDP_NB_ALSO, "A1") in text
    _n2_once(text, "A1")


def test_row_23_both_similar(qapp):
    j = _judge()
    _read(j, "A1", nb=True)
    _read(j, "B1", nb=True)
    v = _settle(j)["A1"]
    assert v.flag == pf.FLAG_CONFIRMED
    assert (v.pe_state, v.nb_state) == ("peer", "peer")
    assert v.peer_locs == v.nb_peer_locs == ("B1",)
    text, lines = _card(qapp, "A1", v, pe=True, nb=True)
    for t in (M._CARD_PEER_2_ONE.format(locs="B1"), _limit_yellow("A1"),
              M._CARDS_NB_PEER_ONE.format(locs="B1"),
              _nb_fmt(M._CARDP_NB_YELLOW, "A1")):
        assert t in text, t


def test_row_24_pe_learned_nb_similar(qapp):
    j = _judge()
    _learned(j)
    long = tuple(1.2 * s for s in SHIFT)
    _read(j, "B1", BLUE, long, pe=False, nb=True)
    v = _read(j, "A1", BLUE, long, nb=True)
    assert v.flag == pf.FLAG_LEARNED
    assert (v.pe_state, v.nb_state) == ("learned", "peer")
    text, lines = _card(qapp, "A1", v, pe=True, nb=True)
    assert M._CARD_RANGE_LEARNED_1 in lines
    assert M._CARDS_NB_PEER_ONE.format(locs="B1") in text
    assert _nb_fmt(M._CARDP_NB_YELLOW, "A1") in text


def test_row_25_pe_similar_nb_corrected():
    j = _judge()
    _read(j, "B1")
    _read(j, "A1", BLUE, (2.0, -5.0, 6.0), pe=False, nb=True)
    v = _read(j, "A1")                    # re-read: past the limit, NB gone
    v = _settle(j)["A1"]
    assert _colour(v) == "yellow" and (v.pe_state, v.nb_state) == ("peer", "")


def test_row_26_pe_learned_nb_corrected():
    j = _judge()
    _learned(j)
    _read(j, "A1", BLUE, (2.0, -5.0, 6.0), pe=False, nb=True)
    v = _read(j, "A1", BLUE, tuple(1.2 * s for s in SHIFT))
    assert v.flag == pf.FLAG_LEARNED and v.nb_state == ""


def test_row_27_pe_corrected_nb_red(qapp):
    j = _judge()
    _read(j, "A1", nb=True)
    v = _read(j, "A1", BLUE, (2.0, -5.0, 6.0), pe=False, nb=True)
    assert v.flag is pf.FLAG_RED and (v.pe_state, v.nb_state) == ("", "red")
    assert v.pe_corrected
    text, _ = _card(qapp, "A1", v, pe=False, nb=True)
    assert _nb_fmt(M._CARDP_NB_RED, "A1") in text
    assert M._CARDS_PE_CORRECTED not in text


def test_row_28_pe_corrected_nb_similar(qapp):
    j = _judge()
    _read(j, "A1", nb=True)
    near = (2.0, -5.0, 6.0)
    _read(j, "B1", BLUE, near, pe=False, nb=True)
    v = _read(j, "A1", BLUE, near, pe=False, nb=True)
    v = _settle(j)["A1"]
    assert v.flag == pf.FLAG_CONFIRMED
    assert (v.pe_state, v.nb_state) == ("", "peer") and v.pe_corrected
    text, lines = _card(qapp, "A1", v, pe=False, nb=True)
    assert M._CARDS_NB_PEER_ONE.format(locs="B1") in text
    assert M._CARDS_PE_CORRECTED in text


def test_row_29_pe_corrected_nb_reread():
    j = _judge()
    _read(j, "A1", BLUE, (12.0, 10.0, 10.0), nb=True)       # ΔE 18.5
    v = _read(j, "A1", BLUE, (11.0, 9.5, 9.0), pe=False, nb=True)
    assert v.flag == pf.FLAG_CONFIRMED and v.nb_state == "reread"


def test_row_30_both_corrected_names_both(qapp):
    j = _judge()
    _read(j, "A1", nb=True)
    v = _read(j, "A1", BLUE, (0.5, 0.5, 0.5), pe=False, nb=False)
    assert v.flag == pf.FLAG_CORRECTED and v.corrected_by == "neighbour"
    text, lines = _card(qapp, "A1", v, pe=False, nb=False)
    assert M._CARD_GREEN_HEAD in lines
    assert M._CARDP_GREEN_NB.format(de=_ab(pf._norm(SHIFT)), loc="A1") in text


def test_row_31_nb_reread_differently_still_red():
    j = _judge()
    _read(j, "A1", BLUE, (2.0, -5.0, 6.0), pe=False, nb=True)
    v = _read(j, "A1", BLUE, (8.0, -5.0, 6.0), pe=False, nb=True)
    assert v.flag is pf.FLAG_RED and v.nb_state == "red"
    assert "A1" in j._pending


def test_row_32_a_reread_covers_a_later_neighbour_suspicion():
    j = _judge()
    _read(j, "A1")
    _read(j, "A1")                                        # Y-re
    v = _read(j, "A1", nb=True, live=False)               # a later strip
    assert v.flag == pf.FLAG_CONFIRMED
    assert (v.pe_state, v.nb_state) == ("reread", "reread")


def test_row_33_the_peer_read_again_differently_turns_it_red():
    j = _judge()
    _read(j, "A1")
    _read(j, "B1")
    assert _settle(j)["A1"].flag == pf.FLAG_CONFIRMED
    _read(j, "B1", BLUE, _add(SHIFT, (0.0, 10.0, 0.0)))   # B1 unsettled
    assert _settle(j)["A1"].flag is pf.FLAG_RED


def test_row_34_the_neighbour_check_switched_off():
    """Off, the tab passes no suspect: the patch error limit alone."""
    j = _judge()
    _read(j, "A1", nb=False)
    v = _read(j, "B1", nb=False)
    assert v.flag == pf.FLAG_CONFIRMED and v.nb_state == ""


def test_row_35_reopened_from_disk():
    """Y-re, R* and G come back from the memory file; Y-sim is worked out
    again from the readings."""
    j = _judge()
    _read(j, "A1")
    _read(j, "A1")                                           # Y-re
    _read(j, "C1", _add(BLUE, (0, 40, 0)))
    _read(j, "C1", _add(BLUE, (0, 40, 0)), _add(SHIFT, (0.0, 10.0, 0.0)))
    _read(j, "D1", _add(BLUE, (40, 0, 0)))
    _read(j, "D1", _add(BLUE, (40, 0, 0)), (0.2, 0.2, 0.2), pe=False)  # G
    _read(j, "E1", _add(BLUE, (0, 0, 40)))
    _read(j, "F1", _add(BLUE, (2, 0, 40)))                   # Y-sim pair
    _settle(j)
    memory = j.export()
    assert memory["E1"] == {"kind": "peer", "test": "pe", "with": ["F1"]}
    k = _judge()
    k.load(memory)
    out = {
        "A1": _read(k, "A1", live=False),
        "C1": _read(k, "C1", _add(BLUE, (0, 40, 0)),
                    _add(SHIFT, (0.0, 10.0, 0.0)), live=False),
        "D1": _read(k, "D1", _add(BLUE, (40, 0, 0)), (0.2, 0.2, 0.2),
                    pe=False, live=False),
        "E1": _read(k, "E1", _add(BLUE, (0, 0, 40)), live=False),
        "F1": _read(k, "F1", _add(BLUE, (2, 0, 40)), live=False),
    }
    out.update(k.rejudge())
    assert out["A1"].flag == pf.FLAG_CONFIRMED and out["A1"].prev_de
    assert out["C1"].flag is pf.FLAG_RED and out["C1"].unsettled
    assert out["D1"].flag == pf.FLAG_CORRECTED
    assert out["E1"].flag == pf.FLAG_CONFIRMED and out["E1"].peer_locs == ("F1",)


def test_the_memory_names_the_test_of_neighbour_check_peers():
    j = _judge()
    _read(j, "A1", nb=True)
    _read(j, "B1", nb=True)
    _read(j, "C1", _add(BLUE, (0, 40, 0)), pe=False, nb=True)
    _read(j, "D1", _add(BLUE, (0, 40, 0)), pe=False, nb=True)
    _settle(j)
    out = j.export()
    assert out["A1"] == {"kind": "peer", "test": "pe+nb", "with": ["B1"]}
    assert out["C1"] == {"kind": "peer", "test": "nb", "with": ["D1"]}


# ---- the neighbour check itself still compares within one strip ------------------
def test_the_neighbour_check_still_takes_neighbours_from_the_same_strip():
    """Knut, #182 6078174421 ("neighbours should come from any strip") and
    6092540253 ("Neighbours are not restricted to other strips"): the CHECK
    compares with patches of its own strip too (calibration charts hold
    their ramps on one strip). Only a CONFIRMATION needs another strip."""
    from workflow.neighbour_check import NeighbourCheck
    nc = NeighbourCheck(radius=15.0, limit=5.0)
    base = [40.0, 42.0, 44.0]
    for n, f in enumerate((1.0, 1.01, 1.02), 1):
        nc.set_reading(f"A{n}", [v * f for v in base],
                       [v * f * 0.9 for v in base], "A")
    nc.evaluate()
    found = nc.finding("A1")
    assert found is not None and set(found.compared) == {"A2", "A3"}


def test_a_list_cut_short_ends_with_one_stop(qapp):
    """More than three similar patches: "B1, C1, D1…", never "D1…."."""
    j = _judge()
    for loc in ("A1", "B1", "C1", "D1", "E1"):
        _read(j, loc)
    v = _settle(j)["A1"]
    text, _ = _card(qapp, "A1", v, pe=True, nb=False)
    assert "read in other strips: B1, C1, D1…" in text and "…." not in text


# ---- review of beta 8: the on-screen matrix's two card faults -----------------
def test_row_09_card_carries_no_range_block(qapp):
    """§10.12.5 row 9 names no range block (row 10 has none either); the
    card showed "Colour range: …" and "1 of 3 confirmations so far"."""
    j = _judge()
    _read(j, "A1", pe=False, nb=True)
    v = _read(j, "A1", pe=False, nb=True)
    assert v.flag == pf.FLAG_CONFIRMED and v.nb_state == "reread"
    text, lines = _card(qapp, "A1", v, pe=False, nb=True)
    rng = M._CARD_RANGE.split("{")[0].strip()
    assert rng not in text
    assert M._CARD_RANGE_SO_FAR.format(k=1) not in text


def test_row_04_card_keeps_its_range_block(qapp):
    j = _judge()
    _read(j, "A1")
    v = _read(j, "A1")
    assert v.flag == pf.FLAG_CONFIRMED and v.pe_state == "reread"
    text, lines = _card(qapp, "A1", v, pe=True, nb=False)
    assert M._CARD_RANGE_SO_FAR.format(k=1) in text


def test_row_12_card_says_how_far_the_range_has_got(qapp):
    """§10.12.5 row 12 lists the range block, which includes
    _CARD_RANGE_SO_FAR; the "RED FOR BOTH REASONS" card left it out."""
    j = _judge()
    _read(j, "R1", REFS["R1"])
    _read(j, "R1", REFS["R1"])                # one confirmation in blue
    v = _read(j, "A1", nb=True)
    v = _settle(j).get("A1", v)
    assert v.flag is pf.FLAG_RED and (v.pe_state, v.nb_state) == ("red", "red")
    assert v.range_k == 1
    text, lines = _card(qapp, "A1", v, pe=True, nb=True)
    assert M._CARD_RANGE_SO_FAR.format(k=1) in text
    assert M._CARD_RANGE_SAME.format(locs="R1") in text
