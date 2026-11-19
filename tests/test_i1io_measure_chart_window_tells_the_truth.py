"""THE MEASURE CHART WINDOWS TELL THE TRUTH SINCE THE TABLE MEASURES (4.3.49).

M-I1IO-MEASURE-CHART and M-I1IO-MEASURE-CHART-PAGES (and the crosses
paragraph of both) said "ChromIQ cannot drive the table itself yet; that is
being prepared for a later version". Since 4.3.45 START MEASUREMENT drives the
table (a Beta) for every i1iO 2 + i1Pro 2 chart with a readable side file in a
run, calibration or verification folder (`_started_the_table_drive`,
`drivable_sheet`), so these windows are only shown for an i1iO chart the table
is not driven with, for example one opened from another folder. They now say
that, how to make a chart ChromIQ drives the table with, and offer i1Profiler
second. 4.3.47 did the same for M-I1IO-NOT-YET
(`test_i1io_not_yet_says_the_side_file_is_missing.py`).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow import measurement_messages as M

# ("a later version may ask you to print the chart again" is about the
# layout, and stays true)
_STALE = ("cannot drive the table itself yet", "prepared for a later version",
          "being prepared", "Until then", "comes in a later version")

_NUMS = {"cols": 24, "rows": 22, "p1": "A1", "p2": "V1", "p3": "V24",
         "pages": 1, "labelled": True, "crosses": True}
_SHEETS = [{"page": k, "pages": 2, "cols": 24, "rows": 22 if k == 1 else 9,
            "p1": "A1", "p2": "V1", "p3": "V24", "labelled": True}
           for k in (1, 2)]


def _windows():
    yield "one page", M.i1io_measure_chart_window(dict(_NUMS), by_hand=False)
    yield "one page, by hand", M.i1io_measure_chart_window(dict(_NUMS),
                                                           by_hand=True)
    yield "pages", M.i1io_measure_chart_pages_window(_SHEETS, True, False)


@pytest.mark.parametrize("name,window", list(_windows()))
def test_no_window_says_the_table_cannot_be_driven_yet(name, window):
    title, body = window
    for stale in _STALE:
        assert stale not in title + body, (name, stale)
    first = body.split("\n\n")[0]
    # what is true today: the table is driven, but not with this chart
    assert "ChromIQ can drive the table itself (a Beta), but not with this " \
           "chart." in first
    assert "“.i1io.json”" in first
    # how to get a chart it drives the table with, with the app's own names
    assert "Create Chart tab" in first and "“i1iO 2 + i1Pro 2”" in first
    assert "Print Chart tab" in first and "Start Measurement" in first
    # and i1Profiler is the second way, not "until then"
    assert body.split("\n\n")[1].startswith("You can also measure")
    # the crosses are ChromIQ's own table measurement, never "later"
    assert "on a chart that ChromIQ drives the table with" in body
    assert "—" not in title + body and "{" not in body


def test_the_crosses_line_of_the_parts_is_the_same_text():
    assert M.tr(M._I1IO_MC_CROSSES) in M.M_I1IO_MEASURE_CHART_PARTS.body
    for stale in _STALE:
        assert stale not in M._I1IO_MC_CROSSES_PAGES


@pytest.mark.parametrize("code", sorted(
    p.stem for p in (Path(__file__).resolve().parents[1] / "data" / "i18n")
    .glob("*.json") if p.stem != "en" and "." not in p.stem))
def test_every_language_has_the_new_texts(code):
    d = json.loads((Path(__file__).resolve().parents[1] / "data" / "i18n"
                    / f"{code}.json").read_text(encoding="utf-8"))
    for key in (M.M_I1IO_MEASURE_CHART.body, M.M_I1IO_MEASURE_CHART_PAGES.body,
                M._I1IO_MC_CROSSES, M._I1IO_MC_CROSSES_PAGES,
                M.M_I1IO_MEASURE_CHART_PARTS.body):
        assert key in d and d[key] and d[key] != key, code
        assert "—" not in d[key], code
        # the translated window keeps the steps' paragraphs: one paragraph
        # more than before (the new first one is split in two)
        assert d[key].count("\n\n") == key.count("\n\n"), code


def test_the_window_is_shown_only_for_a_chart_the_table_is_not_driven_with(
        tmp_path):
    """The claim the first paragraph rests on: a chart outside a run,
    calibration or verification folder is not driven (`drivable_sheet`),
    whatever its side file says; the same chart in a run folder is."""
    from ui.i1io_table_window import drivable_sheet
    side = {"table_model": "i1iO 2", "head_model": "i1Pro 2",
            "pages": [{"strips": []}]}
    loose = tmp_path / "elsewhere" / "chart.ti2"
    inrun = tmp_path / "proj" / "runs" / "run1" / "chart.ti2"
    for ti2 in (loose, inrun):
        ti2.parent.mkdir(parents=True)
        ti2.write_text("CTI2\n", encoding="utf-8")
        ti2.with_name("chart.i1io.json").write_text(json.dumps(side),
                                                    encoding="utf-8")
    assert drivable_sheet(loose) is None
    assert drivable_sheet(inrun) is not None
