"""b15 item 10 (Knut #182 6065640028), in the words Knut approved for beta 17
(6078174421, 6084176226): every hover card says, under "Measured", how far
the patch is from its expected colour compared with the patches nearest to it
in colour, flagged or not. The number is Knut's four steps' (its own error
minus the median of its neighbours' errors, `NeighbourCheck.comparison`), so
the card and the red outline never disagree; with fewer than 2 such patches
read the card says so. Since beta 17 on every chart type, with outlines."""
from __future__ import annotations

import pytest

from tests.test_neighbour_check_in_the_measure_tab import (  # noqa: F401
    _card, _info, _read_all, _strip, _tab, _text, qapp)
from workflow import measurement_messages as M


def _lines(tab, loc):
    return _card(_info(tab, loc))


def _sentence(tab, loc):
    """The comparison line the card shows, from the check's own figures.
    Since 4.3.5 beta 3 in M-PATCH-CARD-PLAIN's words (approved by Knut and
    Basti, 2026-10-13): the neighbours' median, the patch's own colour error
    and the difference, each with its unit; the sign is still the word."""
    n, fu, own, median = tab._nb_check.comparison_detail(loc)
    d = f"{abs(fu):.2f}"
    ab = "ΔE*ab {:.2f}".format
    if d == "0.00":
        line = M._CARDP_NBC_EQUAL
    else:
        line = M._CARDP_NBC_CLOSER if fu < 0 else M._CARDP_NBC_FURTHER
    return line.format(n=n, d="ΔE*ab " + d, own=ab(own), median=ab(median))


def _flat(lines):
    return " ".join(_text(lines).split())


def test_a_clean_patch_shows_its_comparison(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab)
    n, fu = tab._nb_check.comparison("C5")
    assert n >= 2
    lines = _lines(tab, "C5")
    assert _sentence(tab, "C5") in _flat(lines)
    # under the measured colour, above anything about an outline
    first = next(i for i, l in enumerate(lines)
                 if l.startswith(f"The {n} patches"))
    assert first > lines.index("Measured")


def test_the_misread_shows_the_figure_the_check_used(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    f = tab._nb_check.finding("D6")
    assert f.suspect and f.further > 0
    assert (f"this one stands out by ΔE*ab {f.further:.2f}."
            in _flat(_lines(tab, "D6")))
    assert _sentence(tab, "D6") in _flat(_lines(tab, "D6"))


def test_its_neighbours_read_closer_than_it(qapp, tmp_path):
    """The sign is the word (Knut 6078174421: "further from" is replaced
    with "closer to" when below 0, and at 0.0 no value is shown)."""
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    for loc in tab._nb_check.finding("D6").compared:
        assert _sentence(tab, loc) in _flat(_lines(tab, loc))


def test_too_few_neighbours_says_so(qapp, tmp_path):
    tab = _tab(tmp_path, settings={"patch_neighbour_radius_estimated": 1.0})
    tab._on_strip_measured(_strip("A"))
    text = _flat(_lines(tab, "A6"))
    assert M._CARDP_NBC_FEW in text
    assert "patches most similar to it are" not in text


def test_the_card_follows_later_strips(qapp, tmp_path):
    tab = _tab(tmp_path, settings={"patch_neighbour_radius_estimated": 6.0})
    tab._on_strip_measured(_strip("A"))
    assert M._CARDP_NBC_FEW in _flat(_lines(tab, "A6"))
    tab._on_strip_measured(_strip("B"))
    tab._on_strip_measured(_strip("C"))
    n, fu = tab._nb_check.comparison("A6")
    assert n >= 2
    assert _sentence(tab, "A6") in _flat(_lines(tab, "A6"))


@pytest.mark.parametrize("case", ["verification", "calibration"])
def test_on_verification_and_calibration_charts_with_outlines(
        qapp, tmp_path, monkeypatch, case):
    """Beta 17 (Knut 6070058549 answer 3, 6082015002): the check runs there,
    so the card's figure is the check's and a misread is outlined."""
    folder = tmp_path / ("cal" if case == "calibration" else "run1")
    tab = _tab(folder)
    if case == "verification":
        monkeypatch.setattr(type(tab), "_is_verification_run", lambda self: True)
        monkeypatch.setattr(type(tab), "_expected_is_predicted",
                            lambda self: True)
    _read_all(tab, {"D6": 0.55})
    assert tab._neighbour_check_applies()
    n, fu = tab._nb_check.comparison("D6")
    assert n >= 2 and fu > 0
    text = _flat(_lines(tab, "D6"))
    assert _sentence(tab, "D6") in text
    nb = _info(tab, "D6")["neighbour"]
    assert nb is not None
    limit = 3.0 if case == "verification" else 10.0
    assert nb["limit"] == limit
    # red by the neighbour check alone, or (on a verification, whose patch
    # error limit is 5) by both, with the neighbour line after the limit's
    kind = (M._CARD_KIND_VERIFICATION if case == "verification"
            else M._CARD_KIND_CALIBRATION)
    kw = dict(d=f"ΔE*ab {fu:.2f}", limit=f"ΔE*ab {limit:.2f}", kind=kind)
    assert (M._CARDP_NB_RED.format(**kw) in text
            or M._CARDP_NB_ALSO.format(**kw) in text), text
