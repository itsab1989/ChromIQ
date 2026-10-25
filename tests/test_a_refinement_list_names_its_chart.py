"""A refinement-strips list records the chart it was made for, and the Measure
tab ticks it for you only when it fits the chart you measure now (Basti,
2026-10-25, from jctay's forum post 149834: a list from a check of an earlier
layout was ticked by itself on a rebuilt chart)."""
from __future__ import annotations

import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import profcheck_runner as P                    # noqa: E402

TI2 = """CTI2
CREATED "{when}"
NUMBER_OF_FIELDS 4
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G
END_DATA_FORMAT
NUMBER_OF_SETS 2
BEGIN_DATA
1 A1 {a} 0.0
2 A2 100.0 0.0
END_DATA
"""


def _chart(p: Path, a="50.0", when="Mon"):
    p.write_text(TI2.format(a=a, when=when), encoding="latin-1")
    return p


def test_the_fingerprint_ignores_the_date_and_follows_the_patches(tmp_path):
    a = P.chart_fingerprint(_chart(tmp_path / "a.ti2", when="Mon"))
    b = P.chart_fingerprint(_chart(tmp_path / "b.ti2", when="Tue"))
    c = P.chart_fingerprint(_chart(tmp_path / "c.ti2", a="51.0"))
    assert a and a == b and a != c


def test_a_list_for_this_chart_fits_and_one_for_another_does_not(tmp_path):
    chart = _chart(tmp_path / "x.ti2")
    lst = P.write_refine_strips(tmp_path, "x", [("A", 3.0)], chart=chart)
    assert P.refine_list_fingerprint(lst) == P.chart_fingerprint(chart)
    assert P.parse_refine_strips(lst) == ["A"], "the strips must still read"
    assert P.refine_list_fits_chart(lst, chart) == ""
    _chart(chart, a="60.0")                 # the chart is built again
    assert P.refine_list_fits_chart(lst, chart) == "other_chart"


def test_an_old_list_counts_as_not_matching_when_the_chart_is_newer(tmp_path):
    lst = tmp_path / "Refine_Strips_x.txt"
    lst.write_text("# CHROMIQ_REFINE_STRIPS_V1\nA\t3.00\n", encoding="utf-8")
    old = time.time() - 3600
    os.utime(lst, (old, old))
    chart = _chart(tmp_path / "x.ti2")
    assert P.refine_list_fits_chart(lst, chart) == "older_than_chart"
    os.utime(chart, (old - 60, old - 60))
    assert P.refine_list_fits_chart(lst, chart) == ""


def test_the_measure_tab_asks_the_rule_and_explains(qapp):
    import inspect
    from ui.tabs import tab_measure
    src = inspect.getsource(tab_measure)
    assert "refine_list_fits_chart(" in src
    assert "rcb.setChecked(not why)" in src
    assert "setToolTip(tip)" in src
