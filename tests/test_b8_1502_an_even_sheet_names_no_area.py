"""B8-1502 (beta 45 challenge round 3, territory A): on an even sheet the
report named the first ninth "furthest from the average" at 0.00 ΔE00.

The filter (B8-1476) takes an area's difference from the average to 0 when the
noise explains all of it, and on about 2 % of even sheets it does so for all
nine. `worst_area` is then argmax of nine zeros, area 0, and the note named a
part of the sheet as off when none is. The worst pair has the same tie on
about 0.3 %. Knut was told (#182 5857381652): "It will say instead that no area
differs".

OFFSCREEN: a data check of the note's text; no window is involved.
"""
from __future__ import annotations

import numpy as np

from workflow import measurement_report as MR
from ui.dialogs.measurement_report_dialog import (
    _evenness_where_sentence, _evenness_worst_area_sentence)

NO_AREA = ("On the measured chart, once the noise's average share is taken "
           "out, no ninth of the page differs from the average of all nine.")
NO_PAIR = "No two ninths differ from each other."


def _page(per_band_strips: int, per_band_rows: int):
    s, r = 3 * per_band_strips, 3 * per_band_rows
    return MR.evenness_grid_from_layout([s], r, s * r, coverage=[1.0]), s * r


def _an_even_sheet_the_filter_takes_to_zero():
    """The first noise-only sheet, by seed, whose nine areas all read 0 from
    the average once filtered. Deterministic: the same seed every run."""
    g, n = _page(3, 4)
    for seed in range(2000):
        rng = np.random.default_rng(seed)
        b = MR.evenness_from_residuals(g, rng.normal(0, 1.1, (n, 3)),
                                       shuffles=5)
        if b["eligible"] and max(a["de_from_mean"] for a in b["areas"]) == 0:
            return b
    raise AssertionError("no all-zero sheet in 2000 seeds; the filter changed")


def test_an_even_sheet_that_reads_zero_everywhere_names_no_area():
    """MUTATION, proven red: drop the `_shown_above_zero` check in
    `_evenness_worst_area_sentence` (the note names strips 1 to 3 at 0.00)."""
    block = _an_even_sheet_the_filter_takes_to_zero()
    rep = {"evenness": block}
    first = _evenness_worst_area_sentence(rep)
    assert first == NO_AREA, first
    assert "furthest from the average" not in _evenness_where_sentence(rep)


def test_a_pair_that_reads_zero_is_not_named():
    """MUTATION, proven red: always name the worst pair."""
    block = _an_even_sheet_the_filter_takes_to_zero()
    block = dict(block, pairwise=0.0)
    s = _evenness_where_sentence({"evenness": block})
    assert NO_PAIR in s and "furthest apart" not in s, s


def test_a_sheet_with_a_real_difference_still_names_it():
    """The ordinary case is untouched: one ninth well off is named, with its
    figure, and so is the pair. Slots in the grid's own order, strip by strip
    (the construction `test_evenness_filter_and_converted_limits._page` uses)."""
    g, n = _page(3, 4)
    s, r = 9, 12
    st, rw = np.meshgrid(np.arange(s), np.arange(r), indexing="ij")
    area = (MR._bands_of(st.ravel(), np.full(n, s)) * 3
            + MR._bands_of(rw.ravel(), np.full(n, r)))
    rng = np.random.default_rng(3)
    resid = rng.normal(0, 0.3, (n, 3))
    resid[area == 4, 0] += 3.0
    b = MR.evenness_from_residuals(g, resid, shuffles=5)
    assert b["worst_area"] == 4
    sentence = _evenness_where_sentence({"evenness": b})
    assert "furthest from the average of all nine is" in sentence, sentence
    assert "The two ninths furthest apart are" in sentence, sentence
