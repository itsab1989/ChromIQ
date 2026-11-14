"""The ``.txf`` makes i1Profiler compute exactly ChromIQ's grid.

i1Profiler computes the grid itself (REQUIREMENTS §1). The `.txf` gives it a
page half a patch larger than ChromIQ's grid both ways
(`workflow.isis.export.design_for`), so its rule finds Cmax = C and Rmax = R;
and the rule is a fixed point, split(N, C, R) == (C, R, P), so it lays out
ChromIQ's sheet. The study proved the fixed point on 9,849,000 cases
(`scripts/fixed_point_mine.py`); this samples it, and runs the whole chain
(ChromIQ's layout -> side file -> .txf design -> i1Profiler's rule) over a
spread of pages and options."""
from __future__ import annotations

import itertools
import random

import pytest

from workflow.isis import chart as C
from workflow.isis import export as X


def test_the_rule_is_a_fixed_point_sampled():
    rng = random.Random(20261114)
    for _ in range(20000):
        N = rng.randint(1, 3000)
        cmax = rng.randint(1, 49)
        rmax = rng.randint(1, 67)
        c, r, p = C.split(N, cmax, rmax)
        assert C.split(N, c, r) == (c, r, p), (N, cmax, rmax)


PAPERS = [(210, 297), (215.9, 279.4), (148, 210), (127, 178), (203.2, 254),
          (297, 420), (279.4, 431.8), (329, 483), (297, 210)]


@pytest.mark.parametrize("paper,model,tight,bc,header,pw,ph,N", [
    (p, m, t, b, h, pw, ph, n)
    for p, m, t, b, h, (pw, ph), n in itertools.islice(itertools.product(
        PAPERS, ("standard", "xl"), (False, True), (False, True),
        (32.0, 56.0, 80.0), ((6, 6), (8, 7), (20, 20), (7.25, 6.5)),
        (4, 24, 100, 957, 2500)), 0, None, 37)])
def test_the_txf_page_forces_chromiqs_grid(paper, model, tight, bc, header,
                                           pw, ph, N):
    kw = {"patch_w": pw, "patch_h": ph, C.MODEL_KEY: model,
          C.TIGHT_KEY: tight, C.BARCODE_KEY: bc, C.HEADER_KEY: header}
    w, h = paper
    try:
        opts, g, s = C.layout_for(N, w, h, kw)
    except C.IsisSheetRefused:
        return
    side = C.side_doc(s, paper=f"{w}x{h}", name="t", title="t")
    d = X.design_for(side)
    assert X.i1profiler_grid(d, N) == (g.C, g.R, g.P)
