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

Since 4.3.5 beta 3 the card shows M-PATCH-CARD-PLAIN, approved by Knut and
Basti on 2026-10-13, in place of the beta-17 lines; the tests below assert
those words, and the units stand between the two closing topics.
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


# "nb_detail" as the Measure tab gives it (n, figure, own, median): since
# 4.3.5 beta 3 the card speaks in M-PATCH-CARD-PLAIN's words, approved by
# Knut and Basti on 2026-10-13, which name the own and the median figure.
CASES = {
    "quiet": {"nb_compare": lambda loc: (4, -1.2),
              "nb_detail": lambda loc: (4, -1.2, 20.8, 22.0)},
    "quiet_equal": {"nb_compare": lambda loc: (3, 0.004),
                    "nb_detail": lambda loc: (3, 0.004, 20.8, 20.8)},
    "few": {"nb_compare": lambda loc: (1, 0.0),
            "nb_detail": lambda loc: (1, 0.0, 20.8, 0.0)},
    "red_neighbour": {"nb_compare": lambda loc: (4, 13.2),
                      "nb_detail": lambda loc: (4, 13.2, 20.8, 7.6),
                      "neighbour": {"n": 4, "further": 13.2, "limit": 10.0}},
    "red_limit": {"warn": True, "fenced": True, "warn_de": 20.0,
                  "kind": "accurate", "accurate": True, "de": 23.41},
    "red_both": {"warn": True, "warn_de": 15.0,
                 "nb_compare": lambda loc: (4, 13.2),
                 "nb_detail": lambda loc: (4, 13.2, 20.8, 7.6),
                 "neighbour": {"n": 4, "further": 13.2, "limit": 10.0}},
    "yellow": {"flag": "confirmed", "prev_de": 13.9, "de": 13.4,
               "neighbour": {"n": 4, "further": 11.4, "limit": 10.0},
               "nb_compare": lambda loc: (4, 11.4),
               "nb_detail": lambda loc: (4, 11.4, 13.4, 2.0)},
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
    # since 4.3.5 beta 3 (M-PATCH-CARD-PLAIN): the units, once per card,
    # between the two topics, each block set apart by an empty line
    units = list(M._CARDP_UNITS)
    assert _text(rows).endswith(" ".join([later, *units,
                                          M._CARD_SEE_PREFS_S])), case
    from ui.tiff_preview import card_wrap
    a = card_wrap(later)
    i = (len(rows) - len(card_wrap(M._CARD_SEE_PREFS_S)) - 1 - len(units)
         - 1 - len(a))
    assert rows[i - 1] == "" and rows[i:i + len(a)] == a
    assert rows[i + len(a)] == "" and rows[i + len(a) + 1:i + len(a) + 3] == units
    t = _text(rows).lower()
    assert "buffer" not in t and "other strips:" not in t
    assert "your limit" not in t and "flag a patch" not in t


def test_the_comparison_sentences(qapp):
    t = " ".join(_text(_rows(CASES["red_neighbour"])[0]).split())
    assert ("The 4 patches most similar to patch K19 are about ΔE*ab 7.60 off their "
            "expected colours. At ΔE*ab 20.80, this one stands out by "
            "ΔE*ab 13.20. (Neighbour check, median of the 4.)") in t
    t = " ".join(_text(_rows(CASES["quiet"])[0]).split())
    assert ("The 4 patches most similar to patch K19 are about ΔE*ab 22.00 off "
            "their expected colours. At ΔE*ab 20.80, this one is ΔE*ab 1.20 "
            "closer to its expected colour than they are.") in t
    t = " ".join(_text(_rows(CASES["quiet_equal"])[0]).split())
    assert ("The 3 patches most similar to patch K19 are about as far off "
            "their expected colours as this one, at ΔE*ab 20.80. Patch K19 "
            "does not stand out from them.") in t
    assert "ΔE*ab 0.0" not in t
    t = " ".join(_text(_rows(CASES["few"])[0]).split())
    assert M._CARDP_NBC_FEW in t and "this one" not in t


def test_the_red_neighbour_card_is_knuts(qapp):
    rows, _t = _rows(CASES["red_neighbour"])
    t = " ".join(_text(rows).split())
    assert ("Red outline: patch K19 stands out by ΔE*ab 13.20 from the "
            "patches most similar in colour. That is more than the neighbour "
            "limit of ΔE*ab 10.00 for profiling charts with estimated "
            "colours. (Neighbour check.) Probably a misread: read patch K19 "
            "again.") in t
    # the second sentence on a line of its own, as in the mock-up
    assert any(r.startswith("Probably a misread: read patch K19") for r in rows)
    assert ("Read patch K19 again to find out. Similar patches read in "
            "other strips that stand out in the same way can also confirm "
            "it." in t)
    # gone since 4.3.5 beta 8 (Knut, #182 6196599132)
    assert "Only its own re-read" not in t
    assert "Same value after a re-read: it is real, keep it for the profile." \
        in t


def test_the_red_limit_card_names_the_limit_and_the_chart_type(qapp):
    t = " ".join(_text(_rows(CASES["red_limit"])[0]).split())
    assert ("Red outline: too far off its expected colour This patch is "
            "ΔE*ab 23.41 off its expected colour. That is more than the patch "
            "error limit of ΔE*ab 20.00 for profiling charts made with a "
            "pre-conditioning profile. Patch K19 also stands out from the other "
            "patches of its strip. (Strip test.)") in t
    t = " ".join(_text(_rows(CASES["verification_red"])[0]).split())
    assert ("This patch is ΔE*ab 7.18 off its expected colour. That is more "
            "than the patch error limit of ΔE*ab 5.00 for verification "
            "charts.") in t
    assert "Far from what the profile predicts." in t


def test_the_yellow_card_says_why_it_was_red(qapp):
    t = " ".join(_text(_rows(CASES["yellow"])[0]).split())
    assert ("Yellow outline: confirmed by a re-read You read this patch "
            "again, and the new reading agrees with an earlier one. So it is "
            "probably not a misread. Patch K19 is ΔE*ab 13.40 off its expected "
            "colour now, and was ΔE*ab 13.90 off at that earlier reading. "
            "(The two readings are within the same-reading tolerance.) "
            "Without that confirmation, patch K19 would be red for standing "
            "out by ΔE*ab 11.40 from the patches most similar in colour, more than the "
            "neighbour limit of ΔE*ab 10.00 for profiling charts with "
            "estimated colours. (Neighbour check.)") in t


def test_red_for_both_reasons(qapp):
    t = " ".join(_text(_rows(CASES["red_both"])[0]).split())
    assert ("Patch K19 also stands out by ΔE*ab 13.20 from the patches most "
            "similar in colour. That is more than the neighbour limit of ΔE*ab "
            "10.00 for profiling charts with estimated colours. (Neighbour "
            "check.)") in t
    assert (t.index("more than the patch error limit")
            < t.index("Patch K19 also stands out"))


def test_topics_are_separated_by_empty_lines(qapp):
    rows, _t = _rows(CASES["red_neighbour"])
    sep = rows.index("─" * 30)
    assert rows[sep - 1] == ""
    # since 4.3.5 beta 5 the re-read sentence names the patch and is wrapped
    # by the card (Knut, #182 6167582807)
    for start in ("Read patch K19 again to find out.",
                  "Same value after a re-read:"):
        i = next(j for j, r in enumerate(rows) if r.startswith(start))
        assert rows[i - 1] == "", start


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
