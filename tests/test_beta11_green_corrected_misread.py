"""The green outline: a misread a re-read corrected (Knut, #182 5984277558,
"Ok" to 5984237879).

A patch that was red, by the limit or by the neighbour check, and whose LIVE
re-read is no longer flagged by either, is drawn green. Its card says so in
Knut's approved words; the closing window counts it; it is remembered with
the measurement (kind "corrected", never a reference) and drawn green again
when the measurement is opened; a later live reading that is flagged again
ends it. Green applies on verifications too (the limit check runs there and
a verification can be misread); its line in the closing window does not,
since a verification's closing window carries no misread summary (Knut
5983470377).
"""
from __future__ import annotations

from tests.test_neighbour_check_in_the_measure_tab import (  # noqa: F401
    STRIPS, _card, _flags, _info, _read_all, _strip, _tab, qapp)
from workflow import confirmed_patches as cp
from workflow import measurement_messages as M
from workflow import patch_flags as pf


def test_a_neighbour_misread_read_again_and_fitting_is_green(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    first = _info(tab, "D6")["de"]
    tab._on_strip_measured(_strip("D"))
    assert _flags(tab)["D6"] == pf.FLAG_CORRECTED
    info = _info(tab, "D6")
    assert info["flag"] == "corrected" and info["corrected_by"] == "neighbour"
    lines = _card(info)
    i = lines.index(M._CARD_GREEN_HEAD)
    assert lines[i + 1:i + 4] == [
        M._CARD_GREEN_1.format(de=f"{first:.0f}"), M._CARD_GREEN_NB,
        M._CARD_GREEN_END]
    assert not any("Red outline" in x for x in lines)
    assert tab.corrected_locs() == ["D6"]
    assert M._SUM_CORRECTED_ONE.format(locs="D6") in \
        tab._misread_summary().splitlines()
    assert tab.neighbour_summary_facts()["red"] == []


def test_a_limit_misread_read_again_and_fitting_is_green(qapp, tmp_path):
    tab = _tab(tmp_path, settings={"patch_read_warn_de_estimated": 8.0,
                                   "patch_strip_test_estimated": False,
                                   "patch_neighbour_limit_estimated": 50.0})
    _read_all(tab, {"B3": 0.6, "E9": 0.6})
    assert _flags(tab)["B3"] is True and _flags(tab)["E9"] is True
    tab._on_strip_measured(_strip("B"))
    tab._on_strip_measured(_strip("E"))
    info = _info(tab, "B3")
    assert _flags(tab)["B3"] == pf.FLAG_CORRECTED
    assert info["corrected_by"] == "limit"
    assert M._CARD_GREEN_LIMIT in _card(info)
    assert M._SUM_CORRECTED.format(n=2, locs="B3, E9") in \
        tab._misread_summary().splitlines()


def test_red_again_ends_green(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    tab._on_strip_measured(_strip("D"))
    tab._on_strip_measured(_strip("D", {"D6": 0.55}))
    # The first reading's colour came back: no longer green. Since beta 12 a
    # re-read is compared with EVERY earlier reading (Knut, #182 6045500910),
    # so matching the first one confirms it (yellow) rather than leaving it red.
    assert _flags(tab)["D6"] == pf.FLAG_CONFIRMED
    assert tab.corrected_locs() == []


def test_a_patch_never_red_is_not_green(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab)
    tab._on_strip_measured(_strip("D"))
    assert pf.FLAG_CORRECTED not in _flags(tab).values()


def test_green_is_remembered_and_drawn_again_from_the_file(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    tab._on_strip_measured(_strip("D"))
    stored = tab._flag_judge().export()
    assert stored["D6"]["kind"] == "corrected"
    assert stored["D6"]["by"] == "neighbour"
    clean = cp._clean_entry(stored["D6"])
    assert clean == {"kind": "corrected", "de": round(stored["D6"]["de"], 2),
                     "by": "neighbour"}
    # Opened later: a fresh judge, the memory, then the readings painted.
    other = _tab(tmp_path / "again")
    judge = other._reset_flag_judge()
    assert judge.load({"D6": clean}) == 0
    assert judge.confirmed == []                # never a reference
    patches = [p for c in STRIPS for p in _strip(c)["patches"]]
    other._on_chart_measured({"patches": patches}, live=False,
                             strip_fence=True)
    assert _flags(other)["D6"] == pf.FLAG_CORRECTED


def test_green_on_a_verification_but_no_summary_line(qapp, tmp_path,
                                                     monkeypatch):
    tab = _tab(tmp_path, settings={"patch_read_warn_de_estimated": 8.0,
                                   "patch_strip_test_estimated": False})
    monkeypatch.setattr(type(tab), "_is_verification_run", lambda self: True)
    _read_all(tab, {"B3": 0.6})
    assert _flags(tab)["B3"] is True
    tab._on_strip_measured(_strip("B"))
    assert _flags(tab)["B3"] == pf.FLAG_CORRECTED
    assert tab._misread_summary() == ""


def test_the_ring_is_green_and_distinct():
    from ui.tiff_preview import (_RING_GREEN, _RING_RED, _RING_YELLOW,
                                 _ring_colours)
    ring, _halo = _ring_colours(pf.FLAG_CORRECTED)
    assert ring.name() == _RING_GREEN
    assert len({_RING_GREEN, _RING_RED, _RING_YELLOW}) == 3
    assert ring.green() > 180 and ring.red() < 100


def test_the_green_help_is_the_same_everywhere():
    from ui.dialogs.settings_dialog import GREEN_OUTLINE_HELP as a
    from ui.tabs.tab_measure import GREEN_OUTLINE_HELP as b
    assert a == b and "green outline" in a.lower()


def test_the_approved_words_are_knuts():
    msg = M.CATALOGUE["M-PATCH-CORRECTED"]
    assert msg.approved
    said = ("Green outline: corrected by a re-read. The first reading (ΔE 58 "
            "off) did not fit; the new one does. It replaces the misread.")
    assert (M._CARD_GREEN_HEAD + ". " + M._CARD_GREEN_1.format(de=58) + " "
            + M._CARD_GREEN_NB + " " + M._CARD_GREEN_END) == said
    assert M._SUM_CORRECTED.format(n=2, locs="Y6, AE8") == \
        "2 misreads corrected by a re-read: patches Y6, AE8."
    assert not M.CATALOGUE["M-PATCH-CORRECTED-VARIANTS"].approved


def test_the_same_colour_again_after_a_higher_limit_is_not_green():
    """Red at one limit, read again with the same colour at a higher limit:
    no longer flagged, but nothing was corrected, the reading was right."""
    j = pf.FlagJudge()
    e, m = (50.0, 60.0, -70.0), (40.0, 30.0, -40.0)
    assert j.judge("A1", e, m, 47.0, True).flag is pf.FLAG_RED
    assert j.judge("A1", e, (40.5, 30.5, -40.5), 46.0, False).flag \
        is pf.FLAG_NONE
    assert j.corrected == {}
