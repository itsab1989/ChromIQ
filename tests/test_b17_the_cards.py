"""Beta 17: the patch hover cards in the words Knut approved (#182
6078174421, and the k56 mock-ups of 6083412660, "Yes, good." in 6084176226).

* every card of a patch with 2 or more neighbours: "This patch is ΔE X
  further from / closer to its expected colour than the N patches nearest in
  colour (median)."; at ΔE 0.0 no value: "This patch has equal distance ...";
* a red card: "Red outline: ΔE X further from its expected colour than the N
  patches nearest in colour (median), passing the neighbour limit (L).
  Probably a misread: read it again.";
* no "buffer" and no "read in other strips" anywhere;
* EVERY card ends with "Checked again after each strip is read: ..." (patch
  by patch: "... after each patch is read") and then "See Preferences ▸
  Measurement for threshold values.", an empty line between topics.
"""
from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QWidget

from workflow import measurement_messages as M

BASE = {"loc": "K19", "exp_rgb": (92, 140, 188), "meas_rgb": (118, 128, 150),
        "exp_lab": (55.4, -6.1, -30.2), "meas_lab": (53.6, 1.4, -14.9),
        "de": 20.8, "warn_de": 95.0, "accurate": False, "kind": "estimated"}


def _rows(info, mode="both"):
    from ui.tiff_preview import _PatchInfoTile
    host = QWidget()
    tile = _PatchInfoTile(host)
    tile.set_content({**BASE, **info}, mode)
    return [t for _s, t in tile._rows], tile


def _text(rows):
    return " ".join(r for r in rows if r)


CASES = {
    "quiet": {"nb_compare": lambda loc: (4, -1.2)},
    "quiet_equal": {"nb_compare": lambda loc: (3, 0.04)},
    "few": {"nb_compare": lambda loc: (1, 0.0)},
    "red_neighbour": {"nb_compare": lambda loc: (4, 13.2),
                      "neighbour": {"n": 4, "further": 13.2, "limit": 10.0}},
    "red_limit": {"warn": True, "fenced": True, "warn_de": 20.0,
                  "kind": "accurate", "accurate": True, "de": 23.41},
    "red_both": {"warn": True, "warn_de": 15.0,
                 "nb_compare": lambda loc: (4, 13.2),
                 "neighbour": {"n": 4, "further": 13.2, "limit": 10.0}},
    "yellow": {"flag": "confirmed", "prev_de": 13.9, "de": 13.4,
               "neighbour": {"n": 4, "further": 11.4, "limit": 10.0},
               "nb_compare": lambda loc: (4, 11.4)},
    "green": {"flag": "corrected", "prev_de": 58.0,
              "corrected_by": "neighbour"},
    "unsettled": {"warn": True, "unsettled": [40.0]},
    "verification_red": {"warn": True, "warn_de": 5.0, "de": 7.18,
                         "expected_source": "prediction",
                         "kind": "verification", "accurate": True},
    "no_split": {"warn": True},
}


@pytest.mark.parametrize("case", sorted(CASES))
@pytest.mark.parametrize("pbp", [False, True])
def test_every_card_ends_with_the_two_approved_topics(qapp, case, pbp):
    rows, _t = _rows({**CASES[case], "pbp": pbp},
                     "expected" if case == "no_split" else "both")
    later = M._CARD_LATER_PATCH_S if pbp else M._CARD_LATER_STRIP_S
    assert _text(rows).endswith(later + " " + M._CARD_SEE_PREFS_S), case
    from ui.tiff_preview import card_wrap
    a = card_wrap(later)
    i = len(rows) - len(card_wrap(M._CARD_SEE_PREFS_S)) - 1 - len(a)
    assert rows[i - 1] == "" and rows[i:i + len(a)] == a
    assert rows[i + len(a)] == ""
    t = _text(rows).lower()
    assert "buffer" not in t and "other strips:" not in t
    assert "your limit" not in t and "flag a patch" not in t


def test_the_comparison_sentences(qapp):
    t = _text(_rows(CASES["red_neighbour"])[0])
    assert ("This patch is ΔE 13.2 further from its expected colour than "
            "the 4 patches nearest in colour (median).") in t
    t = _text(_rows(CASES["quiet"])[0])
    assert ("This patch is ΔE 1.2 closer to its expected colour than the 4 "
            "patches nearest in colour (median).") in t
    t = _text(_rows(CASES["quiet_equal"])[0])
    assert ("This patch has equal distance from its expected colour as the 3 "
            "patches nearest in colour (median).") in t
    assert "ΔE 0.0" not in t
    t = _text(_rows(CASES["few"])[0])
    assert M._CARD_NBC_FEW_S in t and "This patch" not in t


def test_the_red_neighbour_card_is_knuts(qapp):
    rows, _t = _rows(CASES["red_neighbour"])
    t = _text(rows)
    assert ("Red outline: ΔE 13.2 further from its expected colour than the "
            "4 patches nearest in colour (median), passing the neighbour "
            "limit (10.0). Probably a misread: read it again.") in t
    # the second sentence on a line of its own, as in the mock-up
    assert "Probably a misread: read it again." in rows
    assert ("Only its own re-read can turn it yellow, not similar patches or "
            "its colour range.") in t
    assert "Same value after a re-read: it is real, keep it for the profile." \
        in t


def test_the_red_limit_card_names_the_limit_and_the_chart_type(qapp):
    t = _text(_rows(CASES["red_limit"])[0])
    assert ("Red outline: a large difference ΔE*ab 23.4 reached the patch "
            "error limit (20.0, profiling charts made with a "
            "pre-conditioning profile), and it stands out from its strip "
            "(strip test).") in t
    t = _text(_rows(CASES["verification_red"])[0])
    assert ("ΔE*ab 7.2 reached the patch error limit (5.0, verification "
            "charts).") in t
    assert "Far from what the profile predicts." in t


def test_the_yellow_card_says_why_it_was_red(qapp):
    t = _text(_rows(CASES["yellow"])[0])
    assert ("Yellow outline: confirmed by a re-read ΔE*ab 13.4, the reading "
            "before 13.9 Red before: ΔE 11.4 further from its expected colour "
            "than the 4 patches nearest in colour (median), passing the "
            "neighbour limit (10.0).") in t


def test_red_for_both_reasons(qapp):
    t = _text(_rows(CASES["red_both"])[0])
    assert ("It is also ΔE 13.2 further from its expected colour than the 4 "
            "patches nearest in colour (median), passing the neighbour limit "
            "(10.0).") in t
    assert t.index("reached the patch error limit") < t.index("It is also")


def test_topics_are_separated_by_empty_lines(qapp):
    rows, _t = _rows(CASES["red_neighbour"])
    sep = rows.index("─" * 30)
    assert rows[sep - 1] == ""
    for start in ("Only its own re-read can turn it yellow,",
                  "Same value after a re-read:"):
        assert rows[rows.index(start) - 1] == "", start


@pytest.mark.parametrize("lang", ["en", "de", "es", "fr", "it", "ja", "nl",
                                  "no", "pl", "pt", "ru", "sv", "uk", "zh_CN"])
def test_every_language_keeps_the_card_narrow(qapp, lang):
    """The sentences are wrapped to the card's width, in every language:
    no line is much wider than the card's own fixed lines."""
    import core.i18n as i18n
    from PyQt6.QtGui import QFontMetrics
    prev = getattr(i18n, "_language", "en")
    try:
        i18n.set_language(lang)
        fixed = set(i18n._catalog.values()) if lang != "en" else set()
        for case in ("red_neighbour", "red_limit", "yellow", "red_both"):
            rows, tile = _rows(CASES[case])
            fm = QFontMetrics(tile._font)
            # lines the card has always broken by hand (their translations
            # are older than beta 17) set the card's width; the wrapped
            # sentences may not stick out beyond it
            hand = [fm.horizontalAdvance(r) for r in rows
                    if r in fixed or r.startswith("─")]
            wrapped = [r for r in rows if r not in fixed]
            widest = max(fm.horizontalAdvance(r) for r in wrapped)
            assert widest <= max([300] + hand), (
                lang, case, widest, max(wrapped, key=fm.horizontalAdvance))
    finally:
        i18n.set_language(prev)
