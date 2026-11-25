"""Item 66: a right page whose last strip is short is filed.

A chart with Randomise off ends with white fill-up patches. With only 4 or 8
real patches in a last strip of 24, the strip check compared white with white:
a page that was read rightly was refused ("strip AD does not fit its own
patches"), 5 of 5. Half or more equal neighbours: only the others can tell.
What was wrong stays refused, and a strip read one patch out of place is seen
by its real patches.
"""
from __future__ import annotations

import numpy as np
import pytest

from tests import i1p_forward as F
from workflow import turned_colour_check as C


@pytest.fixture(autouse=True)
def _beta_on(monkeypatch):
    from workflow.i1io import support
    monkeypatch.setattr(support, "_latched", True)


def _chart(tmp_path, n, seed=3):
    r = np.random.default_rng(seed)
    return F.build_chart(tmp_path / "c",
                         [tuple(r.uniform(0, 100, 3)) for _ in range(n)],
                         randomize=False, seed=seed + 1)


def _match(tmp_path, ti2, page, way, seed=3):
    from workflow.i1io import pages
    sheet = F.load_sheet(ti2, page)
    f = F.measure(sheet, tmp_path / "m.cmxf", F.mistakes(sheet)[way],
                  rng=np.random.default_rng(seed))
    return pages.match_file(f, F.convert(f, tmp_path / "cv"), ti2)


@pytest.mark.parametrize("n", [700, 704, 708, 716, 720])
def test_a_right_page_is_filed_and_a_wrong_one_is_not(tmp_path, n):
    from workflow.i1io import pages
    ti2 = _chart(tmp_path, n)
    assert pages.page_count(ti2) == 2
    for page in (1, 2):
        m = _match(tmp_path, ti2, page, "right")
        assert (m.kind, m.page) == ("one", page), m.reason
    for way in ("half-turn", "mirror-along", "mirror-strips", "transposed",
                "one-patch-along", "one-strip-down", "aim3-one-short",
                "aim2-one-strip-up", "aim1-one-patch-along", "aimed-crosses"):
        assert _match(tmp_path, ti2, 2, way).kind == "refuse", way


ROWS, COLS = 8, 24


def _colours(real, seed=1):
    """(expected, measured) L*a*b* in i1Profiler's order of a chart of ROWS
    strips whose last one has *real* patches and white after them."""
    r = np.random.default_rng(seed)
    E = np.column_stack([r.uniform(10, 95, ROWS * COLS),
                         r.uniform(-60, 60, (ROWS * COLS, 2))])
    last = [c * ROWS + ROWS - 1 for c in range(COLS)]
    E[last[real:]] = (100.0, 0.0, 0.0)
    return E, E * 0.8 + 5 + r.normal(0, 1.0, E.shape), last


@pytest.mark.parametrize("real", [4, 8])
@pytest.mark.parametrize("step", [1, -1])
def test_a_short_strip_read_one_patch_out_of_place_is_seen(real, step):
    E, M, last = _colours(real)
    assert C.judge(E, M, ROWS, COLS).verdict == C.AGREE
    slipped = M.copy()
    slipped[last] = M[np.roll(last, step)]
    j = C.judge(E, slipped, ROWS, COLS)
    assert j.verdict != C.AGREE and j.strip == ROWS - 1, j


#: Other readings in the place of the last strip's (M, its entries).
READ = {
    "right": lambda M, last: M[last],
    "one patch late": lambda M, last: M[np.roll(last, 1)],
    "one patch early": lambda M, last: M[np.roll(last, -1)],
    "one early, past the end": lambda M, last: M[last[1:] + last[-1:]],
    "mirrored": lambda M, last: M[last[::-1]],
    "the strip beside it": lambda M, last: M[[j - 1 for j in last]],
}


@pytest.mark.parametrize("real", [0, 1, 2, 3, 4, 6, 8, 11, 12])
def test_a_last_strip_of_any_length_is_judged_by_something(real):
    """S1 of the review: with 1 or 2 real patches no neighbour can tell, and
    the strip beside it was filed in its place, 16 of 20. Its equals must have
    been read alike, and a patch of its own not as one of them. 20 charts."""
    for way, read in READ.items():
        filed = 0
        for seed in range(20):
            E, M, last = _colours(real, seed)
            got = M.copy()
            got[last] = read(M, last)
            filed += C.judge(E, got, ROWS, COLS).verdict == C.AGREE
        # (nothing but fill-up: its order is nobody's, only another strip is)
        right = way == "right" or (real == 0 and way != "the strip beside it")
        assert filed == (20 if right else 0), (real, way, filed)


@pytest.mark.parametrize("real", [1, 2, 4, 8, 10])
def test_a_paper_far_from_the_foretold_white_refuses_no_right_page(real):
    """The fit of a strip of equals is taken over the patches it compares: the
    fill-up patches' own distance (a paper 40 L* off here) is not theirs."""
    for seed in range(20):
        E, M, last = _colours(real, seed)
        M[last[real:], 0] += 40.0
        assert C.judge(E, M, ROWS, COLS).verdict == C.AGREE, seed


@pytest.mark.parametrize("n", [697, 698, 721, 722])
def test_the_whole_route_with_one_or_two_real_patches(tmp_path, n):
    ti2 = _chart(tmp_path, n)
    from workflow.i1io import pages
    last = pages.page_count(ti2)
    m = _match(tmp_path, ti2, last, "right")
    assert (m.kind, m.page) == ("one", last), m.reason
    for way in ("half-turn", "mirror-along", "one-patch-along",
                "one-strip-down"):
        assert _match(tmp_path, ti2, last, way).kind == "refuse", way


def test_only_a_strip_of_equals_is_judged_by_part_of_it(monkeypatch):
    """Any other strip is judged as it was."""
    E, M, _last = _colours(COLS)
    assert not any(C.row_of_equals(E[C._strip_entries(len(E), ROWS, COLS, r)])
                   for r in range(ROWS))
    before = C.judge(E, M, ROWS, COLS)
    monkeypatch.setattr(C, "row_of_equals", lambda e: False)
    assert C.judge(E, M, ROWS, COLS) == before
