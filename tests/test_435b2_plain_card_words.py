"""4.3.5 beta 2 (Knut, #182 6108217111): the hover-card lines of the patch
error limit and the neighbour check, in words that say which value, which
unit and compared with what (M-PATCH-CARD-PLAIN, §M-PROPOSED).

* hidden until approved: the card shows the approved texts unchanged;
* switched on (a driver's preview, or the approval), every line names its
  number: the colour error (ΔE*ab between the reading and the expected
  colour), the same difference in ΔE00 (the Measurement Report's formula),
  the neighbours' median colour error, the limit and its chart type;
* the yellow card no longer says "Red before" about a verdict worked out on
  the current reading, nor "the reading before 6.70" without a unit;
* Knut's patch D5 (run 2 of Printer_HP_CLJ5550_i1Pro2_ChromIQ, verification
  2026-10-11_00-40-04): ΔE*ab 8.07 on the card is ΔE00 6.46 in the formula
  of the report, and its neighbour figure 6.44 is 8.07 minus the median 1.63;
* v3 (Knut, #182 6134781112): every number carries its unit right before it,
  the units are defined once at the bottom, the difference is a section of
  its own, every sentence ends, and a tall card gets wider (the size rule).
"""
from __future__ import annotations

import dataclasses

import pytest
from PyQt6.QtWidgets import QWidget

from workflow import measurement_messages as M

D5 = {"loc": "D5", "exp_rgb": (140, 86, 74), "meas_rgb": (136, 95, 72),
      "exp_lab": (42.6263, 21.9922, 16.8117),
      "meas_lab": (44.4158, 14.8051, 20.0084),
      "de": 8.07, "expected_source": "prediction", "kind": "verification",
      "accurate": True,
      "nb_compare": lambda loc: (4, 6.44),
      "nb_detail": lambda loc: (4, 6.44, 8.07, 1.63)}
NB = {"n": 4, "further": 6.44, "limit": 5.5}

CASES = {
    "every_card": {},
    "closer": {"nb_compare": lambda loc: (4, -1.2),
               "nb_detail": lambda loc: (4, -1.2, 2.1, 3.3)},
    "few": {"nb_compare": lambda loc: (1, 0.0),
            "nb_detail": lambda loc: (1, 0.0, 8.07, 0.0)},
    "red_neighbour": {"neighbour": NB},
    "red_limit": {"warn": True, "warn_de": 7.5},
    "red_fenced": {"warn": True, "warn_de": 7.5, "fenced": True},
    "red_both": {"warn": True, "warn_de": 7.5, "neighbour": NB},
    "yellow_neighbour": {"flag": "confirmed", "prev_de": 6.70,
                         "neighbour": NB},
    "yellow_limit": {"flag": "confirmed", "prev_de": 6.70, "warn": True,
                     "warn_de": 7.5},
    "unsettled_two": {"warn": True, "warn_de": 5.0, "unsettled": [12.3]},
    "unsettled_three": {"warn": True, "warn_de": 5.0,
                        "unsettled": [12.3, 18.4]},
    "green_neighbour": {"flag": "corrected", "prev_de": 14.2,
                        "corrected_by": "neighbour"},
    "green_limit": {"flag": "corrected", "prev_de": 14.2,
                    "corrected_by": "limit"},
    # v3: every other card type the proposal appears on
    "yellow_peers": {"flag": "confirmed", "peer_locs": ["F3", "H9"],
                     "warn": True, "warn_de": 7.5, "colour_range": "red",
                     "range_k": 1, "range_locs": ["D5"]},
    "yellow_learned": {"flag": "learned", "like_loc": "C3", "warn": True,
                       "warn_de": 7.5, "colour_range": "red", "range_k": 3,
                       "range_locs": ["C3", "D5", "F3"]},
    "red_estimated": {"expected_source": None, "accurate": False,
                      "kind": "estimated", "warn": True, "warn_de": 7.5,
                      "colour_range": "red", "range_k": 1,
                      "range_locs": ["D5"]},
    "red_later_profile": {"expected_source": "estimate_profile_newer",
                          "warn": True, "warn_de": 7.5},
    "unsettled_three_neighbour": {"warn": True, "warn_de": 5.0,
                                  "unsettled": [12.3, 18.4], "neighbour": NB},
}


def _text(info, mode="both") -> str:
    from ui.tiff_preview import _PatchInfoTile
    host = QWidget()
    tile = _PatchInfoTile(host)
    tile.set_content({**D5, **info}, mode)
    return " ".join(t for _s, t in tile._rows if t)


@pytest.fixture
def plain(monkeypatch):
    """The driver-only preview: the proposed words switched on."""
    monkeypatch.setattr(M, "M_PATCH_CARD_PLAIN", dataclasses.replace(
        M.M_PATCH_CARD_PLAIN, approved=True))


def test_the_words_wait_for_approval():
    assert M.M_PATCH_CARD_PLAIN.approved is False
    assert "M-PATCH-CARD-PLAIN" in M.PROPOSED


@pytest.mark.parametrize("case", sorted(CASES))
def test_hidden_the_card_is_unchanged(qapp, case):
    t = _text(CASES[case])
    assert "Colour error" not in t and "colour error" not in t
    assert "ΔE00" not in t
    assert "Without the re-read" not in t


def test_hidden_knuts_yellow_card_reads_as_before(qapp):
    t = _text(CASES["yellow_neighbour"])
    assert "ΔE*ab 8.07, the reading before 6.70" in t
    assert "Red before: ΔE 6.44 further" in t


def _words(t: str) -> str:
    """The card's text with its line breaks undone (it wraps sentences)."""
    return " ".join(t.split())


@pytest.mark.parametrize("case", sorted(CASES))
def test_switched_on_no_old_wording_remains(qapp, plain, case):
    t = _words(_text(CASES[case]))
    for old in ("Red before", "the reading before", "reached the patch error",
                "a large difference", "further from its expected colour",
                "colour than the 4 patches", "ΔE {",
                "(ΔE 14.20 off)", "Without the re-read"):
        assert old not in t, (case, old)
    # Every ΔE on the card names its formula: ΔE*ab or ΔE00, never "ΔE ".
    assert "ΔE " not in t.replace("ΔE00", "").replace("ΔE*ab", ""), case



# v3, Knut #182 6134781112: meaning first, every ΔE with its unit in front.

def test_switched_on_the_difference_is_a_section_of_its_own(qapp, plain):
    rows = _rows({})
    texts = [t for _s, t in rows]
    i = texts.index("Difference between the two colours")
    from ui.tiff_preview import _CardBold
    assert isinstance(texts[i], _CardBold)
    # after both colours, set apart from "Measured" by an empty line
    assert texts.index("Measured") < i and texts[i - 1] == ""
    assert texts[i + 1] == "  ΔE*ab 8.07   ΔE00 6.46"
    t = _words(" ".join(texts))
    assert ("The expected colour is what the run's profile predicts for the "
            "values sent to the printer. The Measurement Report uses ΔE00. "
            "It is closer to how the eye sees colour differences.") in t
    assert ("The 4 patches most similar to it are only about ΔE*ab 1.63 off "
            "their expected colours. At ΔE*ab 8.07, this one stands out by "
            "ΔE*ab 6.44. (Neighbour check, median of the 4.)") in t


@pytest.mark.parametrize("mode", ["expected", "measured"])
def test_switched_on_the_difference_in_every_view_mode(qapp, plain, mode):
    assert "ΔE*ab 8.07   ΔE00 6.46" in _text({}, mode)


@pytest.mark.parametrize("info, basis", [
    ({}, M._CARDP_BASIS_PREDICTED),
    ({"expected_source": None, "accurate": True}, M._CARDP_BASIS_ACCURATE),
    ({"expected_source": None, "accurate": False}, M._CARDP_BASIS_ESTIMATE),
    ({"expected_source": "estimate_profile_newer"}, M._CARDP_BASIS_ESTIMATE),
])
def test_switched_on_the_card_says_what_the_expected_colour_is(
        qapp, plain, info, basis):
    t = _words(_text(info))
    assert basis in t
    others = {M._CARDP_BASIS_PREDICTED, M._CARDP_BASIS_ACCURATE,
              M._CARDP_BASIS_ESTIMATE} - {basis}
    assert not any(o in t for o in others)


def test_switched_on_closer_equal_and_too_few(qapp, plain):
    t = _words(_text(CASES["closer"]))
    assert ("The 4 patches most similar to it are about ΔE*ab 3.30 off their "
            "expected colours. At ΔE*ab 2.10, this one is ΔE*ab 1.20 closer to "
            "its expected colour than they are.") in t
    t = _words(_text({"nb_compare": lambda loc: (3, 0.0),
                      "nb_detail": lambda loc: (3, 0.0, 2.5, 2.5)}))
    assert "at ΔE*ab 2.50. It does not stand out from them." in t
    t = _words(_text(CASES["few"]))
    assert "Not compared with similar patches:" in t
    assert "yet" not in t.split("Not compared with similar patches")[1][:5]


def test_switched_on_knuts_two_yellow_cards(qapp, plain):
    t = _words(_text(CASES["yellow_neighbour"]))
    assert ("You read this patch again, and the new reading agrees with an "
            "earlier one. So it is probably not a misread. It is ΔE*ab 8.07 "
            "off its expected colour now, and was ΔE*ab 6.70 off at that "
            "earlier reading. (The two readings are within the same-reading "
            "tolerance.)") in t
    assert ("Without that confirmation it would be red: it stands out from "
            "the patches most similar to it by ΔE*ab 6.44, more than the "
            "neighbour limit of ΔE*ab 5.50 for verification charts. "
            "(Neighbour check.)") in t
    t = _words(_text(CASES["yellow_limit"]))
    assert ("Without that confirmation it would be red: it is ΔE*ab 8.07 off "
            "its expected colour, more than the patch error limit of ΔE*ab "
            "7.50 for verification charts.") in t


def test_a_yellow_card_nobody_read_again_does_not_speak_of_a_re_read(qapp, plain):
    """The limit line is also shown on a yellow card judged like a patch of
    its colour range, where nothing was read again: the first wording said
    "Without the re-read" there, which was not true."""
    t = _words(_text({"flag": "learned", "like_loc": "C3", "warn": True,
                      "warn_de": 7.5, "colour_range": "red"}))
    assert "Yellow outline: judged like patch C3" in t
    assert "Without that confirmation it would be red" in t
    assert "re-read it would" not in t


def test_switched_on_the_red_cards(qapp, plain):
    t = _words(_text(CASES["red_neighbour"]))
    assert ("Red outline: this patch stands out from the patches most similar "
            "to it by ΔE*ab 6.44. That is more than the neighbour limit of "
            "ΔE*ab 5.50 for verification charts. (Neighbour check.) Probably "
            "a misread: read it again.") in t
    t = _words(_text(CASES["red_both"]))
    assert "Red outline: too far off its expected colour" in t
    assert ("This patch is ΔE*ab 8.07 off its expected colour. That is more "
            "than the patch error limit of ΔE*ab 7.50 for verification "
            "charts.") in t
    assert ("It also stands out from the patches most similar to it by ΔE*ab "
            "6.44.") in t
    t = _words(_text(CASES["red_fenced"]))
    assert "other patches of its strip. (Strip test.)" in t


def test_switched_on_unsettled_and_green(qapp, plain):
    t = _words(_text(CASES["unsettled_two"]))
    assert ("It is ΔE*ab 8.07 off its expected colour now. An earlier reading "
            "was ΔE*ab 12.30 off.") in t
    assert ("This reading and an earlier one are both further off than the "
            "patch error limit of ΔE*ab 5.00 for verification charts, and they "
            "do not agree with each other. So it is not clear yet which one is "
            "right.") in t
    t = _words(_text(CASES["unsettled_three"]))
    # combined review of beta 2: only the earlier readings that were red and
    # past the limit are counted (patch_flags ``unsettled``), so the card says
    # no more than that
    assert "Earlier readings were ΔE*ab 12.30, ΔE*ab 18.40 off." in t
    assert ("3 readings of this patch are further off than the patch error "
            "limit") in t
    assert "You have read this patch" not in t
    t = _words(_text(CASES["green_neighbour"]))
    assert ("The earlier, red reading was ΔE*ab 14.20 off its expected colour "
            "and stood out from the patches most similar to it.") in t
    t = _words(_text(CASES["green_limit"]))
    assert ("more than the patch error limit. The new reading is within the "
            "limit.") in t


# ---- Knut's three rules, on every variant ----------------------------------

import re

_NUMBER = re.compile(r"(?<![\w.*])(\d+\.\d+)")


@pytest.mark.parametrize("case", sorted(CASES))
def test_switched_on_every_number_carries_its_unit(qapp, plain, case):
    """Every decimal on the card stands right after "ΔE*ab " or "ΔE00 ",
    except the colour lines (RGB / Lab, unchanged above the Difference)."""
    rows = [t for _s, t in _rows(CASES[case])]
    body = rows[rows.index("Difference between the two colours"):]
    text = _words(" ".join(body))
    for m in _NUMBER.finditer(text):
        before = text[:m.start()]
        assert before.endswith(("ΔE*ab ", "ΔE00 ")), (case, text[m.start() - 30:m.end()])
    # and no bracketed definition per line any more
    assert "(ΔE*ab" not in text and "(ΔE00" not in text and "CIE76)" not in text


@pytest.mark.parametrize("case", sorted(CASES))
def test_switched_on_the_units_are_defined_once_above_see_preferences(
        qapp, plain, case):
    texts = [t for _s, t in _rows(CASES[case])]
    assert texts.count(M._CARDP_UNITS[0]) == 1
    assert texts.count(M._CARDP_UNITS[1]) == 1
    i = texts.index(M._CARDP_UNITS[0])
    assert texts[i + 1] == M._CARDP_UNITS[1]
    # the last topic: after "Checked again ...", before "See Preferences"
    after = _words(" ".join(texts[i + 2:]))
    assert after == _words(M._CARD_SEE_PREFS_S)
    assert _words(" ".join(texts[:i])).endswith(_words(M._CARD_LATER_STRIP_S))


@pytest.mark.parametrize("case", sorted(CASES))
def test_switched_on_every_card_still_ends_with_the_approved_topics(
        qapp, plain, case):
    t = _words(_text(CASES[case]))
    assert t.endswith(_words(M._CARD_SEE_PREFS_S))
    assert _words(M._CARD_LATER_STRIP_S) in t


#: Lines of OTHER, approved messages that are labels, not sentences: they
#: stand on a line of their own (Knut's "Colour range: red" block).
_LABELS = ("Colour range:", "Confirmed:", "of 3 confirmations so far",
           "Read alike in other strips:")


def _unfinished(info) -> "list[str]":
    """The card's lines that end without punctuation and do not run on by
    design: not a heading (bold, or a colour's name), not a value line, not
    a label, and not the first half of a sentence the approved wording
    breaks by hand (``_card_join_firsts``), which its second half finishes."""
    from ui.tiff_preview import (_CardBold, _PatchInfoTile, _card_join_firsts)
    host = QWidget()
    _KEEP.append(host)
    tile = _PatchInfoTile(host)
    tile.set_content({**D5, **info}, "both")
    joins = _card_join_firsts()
    bad = []
    for i, (sw, t) in enumerate(tile._logical):
        if (i == 0 or sw is not None or not t or isinstance(t, _CardBold)
                or t.startswith("  ") or set(t) == {"─"} or t in joins
                or t in M._CARDP_UNITS
                or any(lab in t for lab in _LABELS)):
            continue
        if not t.rstrip().endswith((".", ".)", ":", "?", ",")):
            bad.append(t)
        elif t.rstrip().endswith((":", ",")):
            # runs on by design: the next line must be its continuation
            nxt = tile._logical[i + 1][1] if i + 1 < len(tile._logical) else ""
            if not nxt or isinstance(nxt, _CardBold):
                bad.append(t)
    return bad


@pytest.mark.parametrize("case", sorted(CASES))
def test_switched_on_every_sentence_is_finished(qapp, plain, case):
    """Knut: "...the reading before 7.71" ended without a full stop and read
    as running on into the next line. On the proposed card every line ends
    with its punctuation, or is a heading, a value line, a label, or the
    first half of a sentence the approved wording breaks by hand."""
    assert _unfinished(CASES[case]) == [], case


def test_the_sentence_check_finds_knuts_line_on_todays_card(qapp):
    """The check has teeth: today's yellow card (hidden proposal) has the
    line Knut quoted, and the check names it."""
    bad = _unfinished(CASES["yellow_neighbour"])
    assert "ΔE*ab 8.07, the reading before 6.70" in bad


def test_switched_on_the_outline_headlines_are_bold(qapp, plain):
    from ui.tiff_preview import _CardBold
    for case, head in (("red_limit", "Red outline: too far off its expected colour"),
                       ("yellow_limit", "Yellow outline: confirmed by a re-read"),
                       ("unsettled_two", "Red outline: the readings do not agree"),
                       ("green_limit", "Green outline: corrected by a re-read")):
        rows = [t for _s, t in _rows(CASES[case])]
        assert head in rows, (case, rows)
        assert isinstance(rows[rows.index(head)], _CardBold), case


def _rows(info, mode="both", max_size=None):
    from ui.tiff_preview import _PatchInfoTile
    host = QWidget()
    tile = _PatchInfoTile(host)
    tile.set_content({**D5, **info}, mode, max_size=max_size)
    rows = list(tile._rows)
    _KEEP.append(host)
    return rows


_KEEP: list = []
