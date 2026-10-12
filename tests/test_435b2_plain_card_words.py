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
  of the report, and its neighbour figure 6.44 is 8.07 minus the median 1.63.
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
                "closer to its expected colour", "ΔE {", "(ΔE 14.20 off)"):
        assert old not in t, (case, old)
    # Every ΔE on the card names its formula: ΔE*ab or ΔE00, never "ΔE ".
    assert "ΔE " not in t.replace("ΔE00 (", "").replace("ΔE*ab", ""), case


def test_switched_on_the_colour_error_and_the_reports_figure(qapp, plain):
    t = _words(_text({}))
    assert ("Colour error: ΔE*ab 8.07 between the measured and the expected "
            "colour (CIE76, L*a*b* D50).") in t
    assert ("The same difference in ΔE00 (CIEDE2000, the formula of the "
            "Measurement Report): 6.46.") in t
    assert ("Neighbour check: its colour error, ΔE*ab 8.07, is 6.44 more than "
            "the median colour error of the 4 patches nearest in expected "
            "colour (ΔE*ab 1.63).") in t


def test_switched_on_knuts_two_yellow_cards(qapp, plain):
    t = _words(_text(CASES["yellow_neighbour"]))
    assert ("Read again, and the two readings are nearly the same colour "
            "(within the same-reading tolerance). Colour error: ΔE*ab 8.07 "
            "now, ΔE*ab 6.70 at the earlier reading.") in t
    assert ("Without the re-read it would be red by the neighbour check: its "
            "colour error is 6.44 more than the median of the 4 patches "
            "nearest in expected colour, above the neighbour limit (5.50, "
            "verification charts).") in t
    t = _words(_text(CASES["yellow_limit"]))
    assert ("Without the re-read it would be red: its colour error, ΔE*ab "
            "8.07, is above the patch error limit (7.50, verification "
            "charts).") in t


def test_switched_on_the_red_cards(qapp, plain):
    t = _words(_text(CASES["red_neighbour"]))
    assert ("Red outline by the neighbour check: its colour error is 6.44 "
            "more than the median of the 4 patches nearest in expected "
            "colour, above the neighbour limit (5.50, verification charts)."
            ) in t
    t = _words(_text(CASES["red_both"]))
    assert "Red outline: the patch error limit" in t
    assert ("Its colour error, ΔE*ab 8.07, is above the patch error limit "
            "(7.50, verification charts).") in t
    assert "It is also red by the neighbour check" in t
    t = _words(_text(CASES["red_fenced"]))
    assert "(strip test)" in t and "other patches of its strip" in t


def test_switched_on_unsettled_and_green(qapp, plain):
    t = _words(_text(CASES["unsettled_two"]))
    assert "Colour error: ΔE*ab 8.07 now, ΔE*ab 12.30 at the earlier reading." in t
    assert "The two readings do not agree" in t and "(5.00, verification charts)" in t
    t = _words(_text(CASES["unsettled_three"]))
    assert "at the earlier readings (ΔE*ab): 12.30, 18.40." in t
    assert "The 3 readings do not agree" in t
    t = _words(_text(CASES["green_neighbour"]))
    assert ("The red reading had a colour error of ΔE*ab 14.20 and failed the "
            "neighbour check; the new reading passes it.") in t
    t = _words(_text(CASES["green_limit"]))
    assert "above the patch error limit; the new reading is not above it." in t


@pytest.mark.parametrize("case", sorted(CASES))
def test_switched_on_every_card_still_ends_with_the_approved_topics(
        qapp, plain, case):
    t = _words(_text(CASES[case]))
    assert t.endswith(_words(M._CARD_LATER_STRIP_S + " " + M._CARD_SEE_PREFS_S))


def test_the_neighbour_figures_the_card_names():
    """own - median is the figure compared with the Neighbour limit."""
    from workflow.neighbour_check import NeighbourCheck
    nc = NeighbourCheck(radius=30.0, limit=5.5)
    nc.set_reading_lab("A1", (50.0, 0.0, 0.0), (50.0, 0.0, 9.0), None)
    for i, off in enumerate((1.0, 2.0, 3.0), start=2):
        nc.set_reading_lab(f"A{i}", (50.0, 1.0 * i, 0.0),
                           (50.0, 1.0 * i, off), None)
    nc.evaluate()
    n, further, own, median = nc.comparison_detail("A1")
    assert (n, further) == nc.comparison("A1")
    assert own == pytest.approx(9.0) and median == pytest.approx(2.0)
    assert further == pytest.approx(own - median)
    assert nc.comparison_detail("nowhere") == (0, 0.0, 0.0, 0.0)


def test_knuts_d5_in_both_formulas():
    """The analysis of 6108217111 in two lines: the card's ΔE*ab 8.07 is
    ΔE00 6.46, the formula of the report's colour accuracy."""
    import math
    from workflow.ti3_analysis import ciede2000
    e, m = D5["exp_lab"], D5["meas_lab"]
    assert math.dist(e, m) == pytest.approx(8.07, abs=0.005)
    assert ciede2000(m, e) == pytest.approx(6.46, abs=0.005)
