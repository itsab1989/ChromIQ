"""b15 item 10 (Knut #182 6065640028, approved by Basti): every hover card of
a patch the neighbour check judges says, under "Measured", how far the patch
is from its expected colour compared with the patches nearest to it in
colour, flagged or not. The number is the neighbour check's own B2+ median
(`NeighbourCheck.comparison`), so the card and the red outline never
disagree; with fewer than 2 such patches read the card says so."""
from __future__ import annotations

import pytest

from tests.test_neighbour_check_in_the_measure_tab import (  # noqa: F401
    _card, _info, _read_all, _strip, _tab, qapp)
from workflow import measurement_messages as M


def _lines(tab, loc):
    return _card(_info(tab, loc))


def test_a_clean_patch_shows_its_comparison(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab)
    n, fu = tab._nb_check.comparison("C5")
    assert n >= 2
    lines = _lines(tab, "C5")
    assert M._CARD_NBC_1.format(n=n) in lines
    word = (M._CARD_NBC_CLOSER if fu < 0 and f"{abs(fu):.1f}" != "0.0"
            else M._CARD_NBC_FURTHER)
    assert word.format(d=f"{abs(fu):.1f}") in lines
    assert M._CARD_NBC_2 in lines
    # under the measured colour, above anything about an outline
    assert lines.index(M._CARD_NBC_1.format(n=n)) > lines.index("Measured")


def test_the_misread_shows_the_figure_the_check_used(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    f = tab._nb_check.finding("D6")
    assert f.suspect and f.further > 0
    lines = _lines(tab, "D6")
    assert M._CARD_NBC_FURTHER.format(d=f"{f.further:.1f}") in lines


def test_its_neighbours_read_closer_than_it(qapp, tmp_path):
    """The sign is the word: a neighbour of the misread is LESS far off than
    the misread is, so its median can only be at or below the clean value."""
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    for loc in tab._nb_check.finding("D6").compared:
        n, fu = tab._nb_check.comparison(loc)
        lines = _lines(tab, loc)
        if fu < 0 and f"{abs(fu):.1f}" != "0.0":
            assert M._CARD_NBC_CLOSER.format(d=f"{abs(fu):.1f}") in lines
        else:
            assert M._CARD_NBC_FURTHER.format(d=f"{abs(fu):.1f}") in lines


def test_too_few_neighbours_says_so(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._on_strip_measured(_strip("A"))          # nothing else read yet
    lines = _lines(tab, "A6")
    assert M._CARD_NBC_FEW in lines and M._CARD_NBC_FEW_2 in lines
    assert not any(l.startswith("Against the") for l in lines)


def test_the_card_follows_later_strips(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._on_strip_measured(_strip("A"))
    tab._on_strip_measured(_strip("B"))
    tab._on_strip_measured(_strip("C"))
    n, _ = tab._nb_check.comparison("A6")
    assert n >= 2
    assert M._CARD_NBC_1.format(n=n) in _lines(tab, "A6")


@pytest.mark.parametrize("case", ["verification", "calibration"])
def test_not_where_the_check_does_not_run(qapp, tmp_path, monkeypatch, case):
    folder = tmp_path / ("cal" if case == "calibration" else "run1")
    tab = _tab(folder)
    if case == "verification":
        monkeypatch.setattr(type(tab), "_is_verification_run", lambda self: True)
    _read_all(tab)
    lines = _lines(tab, "C5")
    assert not any(l.startswith(("Against the", "Not compared")) for l in lines)
