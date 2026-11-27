"""Every way the pages of an i1iSis measurement can go in wrongly is refused
or asked, never filed in silence (part 1 of the i1iSis pieces work; the
sweep of `test_isis_import_several_pages`, in its own file so that each file
stays under two minutes on one worker; review of part 1, S4).

The charts, readings and wrong ways are those of `test_isis_import_several_
pages`: pages swapped, one page twice, the pages in another order, one page
turned, one column or one row off, and every whole-sheet way of item 63.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_isis_import_several_pages import (   # noqa: E402,F401
    ALIKE, ASKS_WRONG, SETS, _assess, _same_colours, beta, charts, page_ways)


@pytest.mark.parametrize("randomize", [False, True])
@pytest.mark.parametrize("name", sorted(SETS))
def test_no_wrong_way_is_filed_in_silence(charts, tmp_path, name, randomize):
    """Pages swapped, a page twice, the pages in another order, one page
    turned or one column off, and every whole-sheet way of item 63: refused
    or asked, never filed without a word (unless the patches really read
    are of the same colours)."""
    c = charts(name, randomize)
    ways = {**c.ways(), **page_ways(c)}
    for way, p in ways.items():
        if _same_colours(c, p) and name != "even":
            continue
        for printer in (None, "low-gamut"):
            v = _assess(c.measure(tmp_path / "m.ti3", p, printer), c)
            assert not v.ok or v.isis_ask_why, (way, printer, "silent")
            if name not in ASKS_WRONG:
                assert not v.ok, (way, printer, v.isis_ask_why)


