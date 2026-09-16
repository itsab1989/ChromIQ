"""B8-226 — the trend dropped a report an older ChromIQ wrote, and said the
opposite of what was on screen.

`_de00_block` writes every accuracy number TWICE, in the new five-metric
spelling and in the old one, and says why in its own comment: *"aliases kept
for the trend series (report_trend reads mean/max/p95)"*. `report_trend` does
copy them into the trend point, with its own comment: *"the mean/max aliases
older points used"*. **Nothing then read them.** The Colour accuracy chart's
five accessors asked for the new keys only, so a report written before the
five-metric vocabulary (ChromIQ before 2026-07-20) carried no value for any
line, `_TrendChart.set_data` dropped the whole point through `has_any`, and the
chart fell into its empty state.

DRIVEN ON SCREEN, combined round 9 (`J1-the-measurement-report.png`): two dated
measurements listed, BOTH ticked, "Show all measurement runs" already on, the
Report Scope saying "No. of Measurements: 2" — and across the graph,

    "A trend graph needs at least two measurement runs. Add another
     measurement — or, if the profile you have loaded already holds more than
     one run, tick "Show all measurement runs" above."

Both instructions were already carried out. The sentence was false, and its
advice could not be acted on.

Only the two metrics that are the SAME arithmetic are mapped, and that is
proved from `_de00_block` itself, where the new key and its alias are written
from one expression. `max_low95` is deliberately left unmapped: today's is the
nearest-rank maximum of the best 95 % and stamps `p95_rule` to say so, and a
report old enough to lack the new key recorded no rule at all.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.dialogs import measurement_report_dialog as mrd      # noqa: E402
from workflow.measurement_report import report_trend         # noqa: E402


def _an_old_report() -> dict:
    """What ChromIQ wrote before the five-metric vocabulary: mean/max/p95 and
    nothing else."""
    return {"created": "2026-05-02T10:15:00", "chart": "Demo",
            "de00": {"mean": 1.4, "max": 9.2, "p95": 3.1},
            "paper_white": {"lab": [95.1, 0.2, -1.0]}}


def _a_new_report() -> dict:
    return {"created": "2026-08-11T22:20:10", "chart": "Demo",
            "de00": {"avg_all": 1.9, "avg_low95": 1.6, "avg_high5": 7.0,
                     "max_all": 11.0, "max_low95": 3.8,
                     "mean": 1.9, "max": 11.0, "p95": 3.8},
            "paper_white": {"lab": [94.8, 0.3, -1.1]}}


# ---- the arithmetic the mapping rests on -------------------------------
def test_the_alias_and_the_new_key_are_the_same_expression():
    """Not an approximation: `_de00_block` writes both from one expression, so
    the mapping is an identity and not a guess."""
    import workflow.measurement_report as mr
    src = inspect.getsource(mr)
    block = src[src.index('"avg_all":'):src.index('"p95":') + 60]
    assert '"avg_all":   round(float(a.mean()), 3)' in block
    assert '"mean":  round(float(a.mean()), 3)' in block
    assert '"max_all":   round(float(a.max()), 3)' in block
    assert '"max":   round(float(a.max()), 3)' in block


def test_only_the_two_safe_metrics_are_mapped():
    """`p95` carries no recorded rule on an old report, so it is NOT mapped to
    "Maximum ΔE, lowest 95%". A line that cannot be trusted gets no point."""
    assert mrd._ACCURACY_ALIAS == {"avg_all": "mean", "max_all": "max"}


@pytest.mark.parametrize("key,expected", [
    ("avg_all", 1.4),
    ("max_all", 9.2),
    ("avg_low95", None),
    ("avg_high5", None),
    ("max_low95", None),
])
def test_an_old_point_answers_for_what_it_carries(key, expected):
    pt = report_trend([_an_old_report()])[0]
    assert mrd._accuracy_value(pt, key) == expected


def test_a_new_point_is_unchanged():
    pt = report_trend([_a_new_report()])[0]
    for key, want in (("avg_all", 1.9), ("avg_low95", 1.6),
                      ("avg_high5", 7.0), ("max_all", 11.0),
                      ("max_low95", 3.8)):
        assert mrd._accuracy_value(pt, key) == want


# ---- the chart, which is what the user sees ----------------------------
@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _accuracy_metrics():
    from PyQt6.QtGui import QColor
    return [(k, QColor("#000000"), (lambda pt, kk=k: mrd._accuracy_value(pt, kk)))
            for k in mrd._ACCURACY_ROW_KEYS]


def test_the_chart_keeps_the_old_point_and_draws_a_trend(qapp):
    series = report_trend([_an_old_report(), _a_new_report()])
    assert len(series) == 2, "report_trend already kept both points"
    chart = mrd._TrendChart()
    chart.set_data(series, _accuracy_metrics())
    assert chart.has_trend(), (
        "the chart dropped the older report and told the user to add a second "
        "measurement, with two of them listed and ticked on screen")


def test_the_dialog_itself_uses_the_alias_reader(qapp):
    """Not a helper nobody calls: the accuracy chart's accessors go through
    it. The same dead-comment shape is what this finding was."""
    src = inspect.getsource(mrd.MeasurementReportDialog._trend_configs)
    assert "_accuracy_value" in src
    assert "pt.get(kk)" not in src, (
        "the accuracy chart reads the raw key again, so an older report is "
        "dropped exactly as before")
