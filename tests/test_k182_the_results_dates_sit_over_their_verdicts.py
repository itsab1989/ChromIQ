"""Report Results: each date heading is centred over its verdict words.

Knut, #182 5951427228 (beta 2): *"the heading of the table (that is the date of
the measurement selected) is not centred above the column with PASS / FAIL /
INFO verdicts. This seems to be for all reports."* The heading was right-aligned
for every metric table, which is right above numbers (Overview) and wrong above
Report Results' centred words.
"""
from __future__ import annotations

import inspect
import os
import re
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.dialogs.measurement_report_dialog import MeasurementReportDialog as D  # noqa: E402


def _html(head_align=None):
    stub = SimpleNamespace(_ZEBRA_BG="#eeeeee")
    stub._metric_table = lambda dates, rows, **kw: D._metric_table(stub, dates, rows, **kw)
    runs = [{"created": "2026-10-01T10:00:00"}, {"created": "2026-10-02T10:00:00"}]
    getters = [("Mean ΔE00", lambda r: "<td align='center'>PASS</td>")]
    kw = {} if head_align is None else {"head_align": head_align}
    return D._chunked_metric_tables(stub, runs, getters, **kw)


def _date_heads(html):
    return re.findall(r"<th align='(\w+)'[^>]*>2026-10-0\d", html)


def test_results_dates_are_centred():
    assert _date_heads(_html("center")) == ["center", "center"]


def test_number_tables_keep_right_aligned_dates():
    assert _date_heads(_html()) == ["right", "right"]


def test_report_results_asks_for_centred_heads():
    src = inspect.getsource(D)
    i = src.index('_h2(tr("Report Results")')
    assert 'head_align="center"' in src[i:i + 400]
