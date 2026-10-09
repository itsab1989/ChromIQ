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


def _sentence(n, fu):
    d = f"{abs(fu):.1f}"
    if d == "0.0":
        return M._CARD_NBC_EQUAL_S.format(n=n)
    return (M._CARD_NBC_CLOSER_S if fu < 0 else M._CARD_NBC_FURTHER_S).format(
        d=d, n=n)


def test_a_clean_patch_shows_its_comparison(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab)
    n, fu = tab._nb_check.comparison("C5")
    assert n >= 2
    lines = _lines(tab, "C5")
    text = _text(lines)
    assert _sentence(n, fu) in text
    # under the measured colour, above anything about an outline
    first = next(i for i, l in enumerate(lines) if l.startswith("This patch"))
    assert first > lines.index("Measured")


def test_the_misread_shows_the_figure_the_check_used(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    f = tab._nb_check.finding("D6")
    assert f.suspect and f.further > 0
    assert M._CARD_NBC_FURTHER_S.format(
        d=f"{f.further:.1f}", n=len(f.compared)) in _text(_lines(tab, "D6"))


def test_its_neighbours_read_closer_than_it(qapp, tmp_path):
    """The sign is the word (Knut 6078174421: "further from" is replaced
    with "closer to" when below 0, and at 0.0 no value is shown)."""
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    for loc in tab._nb_check.finding("D6").compared:
        n, fu = tab._nb_check.comparison(loc)
        assert _sentence(n, fu) in _text(_lines(tab, loc))


def test_too_few_neighbours_says_so(qapp, tmp_path):
    tab = _tab(tmp_path, settings={"patch_neighbour_radius_estimated": 1.0})
    tab._on_strip_measured(_strip("A"))
    text = _text(_lines(tab, "A6"))
    assert M._CARD_NBC_FEW_S in text
    assert "This patch" not in text


def test_the_card_follows_later_strips(qapp, tmp_path):
    tab = _tab(tmp_path, settings={"patch_neighbour_radius_estimated": 6.0})
    tab._on_strip_measured(_strip("A"))
    assert M._CARD_NBC_FEW_S in _text(_lines(tab, "A6"))
    tab._on_strip_measured(_strip("B"))
    tab._on_strip_measured(_strip("C"))
    n, fu = tab._nb_check.comparison("A6")
    assert n >= 2
    assert _sentence(n, fu) in _text(_lines(tab, "A6"))


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
    text = _text(_lines(tab, "D6"))
    assert _sentence(n, fu) in text
    nb = _info(tab, "D6")["neighbour"]
    assert nb is not None
    limit = 3.0 if case == "verification" else 10.0
    assert nb["limit"] == limit
    # red by the neighbour check alone, or (on a verification, whose patch
    # error limit is 5) by both, with the neighbour line after the limit's
    kw = dict(d=f"{fu:.1f}", n=n, limit=f"{limit:.1f}")
    assert (M._CARD_NB_RED_S.format(**kw) in text
            or M._CARD_NB_ALSO_S.format(**kw) in text)
