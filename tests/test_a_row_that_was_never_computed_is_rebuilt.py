"""A report saved before a row existed must not read N-A for ever.

Grey balance and the 30 to 70 per cent tone ramps were added additively, and
the design record says in as many words that the schema was NOT bumped so that
no report on disk would be re-derived. The consequence nobody traced: version
4.2.0 already wrote schema 7 and had no grey balance in its builder at all, so
every report saved by 4.2.0 and the first two betas fails the staleness test, is
never rebuilt, and shows N-A on both grey rows for ever.

Surveyed on one real disk by a challenge round: 58 saved reports, none carrying
a grey block, 33 of them already at schema 7. And the reason printed beside the
N-A says the measurement file could not be read again, which is untrue. It was
never asked for; the number it was hiding was in the same folder.

The rebuild carries the saved verdict across untouched, so this computes rows
that were never computed and re-grades nothing.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measurement_report import REPORT_SCHEMA          # noqa: E402

# THE REAL RULE, not a copy of it. It used to live inline in the loop that
# reads saved reports, so a test could only restate it, and a mutation that
# broke the window left every assertion here green. It is a module-level
# function now for exactly that reason.
from ui.dialogs.measurement_report_dialog import (                # noqa: E402
    _report_needs_rebuilding as _stale)


def test_the_window_uses_this_very_function():
    """Guards the seam: if the loop stops calling it, these tests go blind."""
    import inspect
    from ui.dialogs import measurement_report_dialog as m
    src = inspect.getsource(m.MeasurementReportDialog)
    assert "_report_needs_rebuilding(rep)" in src, (
        "the report loop no longer calls the rule these tests exercise")


def test_a_report_from_4_2_0_is_rebuilt():
    """Current schema, real statistics, and no grey block: exactly what 4.2.0
    wrote. It used to pass the test and never be rebuilt."""
    rep = {"schema": REPORT_SCHEMA, "de00": {"avg_all": 1.2}}
    assert _stale(rep), (
        "a report with no grey balance is treated as current, so its grey rows "
        "read N-A for ever with a reason that is not true")


def test_a_report_missing_only_the_grey_block_is_rebuilt():
    """SEPARATES THE TWO CLAUSES, and the first draft of this file did not.

    Removing the grey clause from the rule left every test green, because the
    ramps clause caught the same fixture. Two clauses that can only be exercised
    together are one clause with a spare.
    """
    rep = {"schema": REPORT_SCHEMA, "de00": {"avg_all": 1.2},
           "ramps_30_70": {"max": 0.8}}
    assert _stale(rep), "a missing grey block alone no longer forces a rebuild"


def test_a_report_missing_only_the_ramps_is_rebuilt():
    rep = {"schema": REPORT_SCHEMA, "de00": {"avg_all": 1.2},
           "grey_balance": {"avg": 1.4}}
    assert _stale(rep)


def test_a_current_report_is_left_alone():
    """The other half. Rebuilding a report that has everything would re-read
    the measurement on every open for nothing."""
    rep = {"schema": REPORT_SCHEMA, "de00": {"avg_all": 1.2},
           "grey_balance": {"avg": 1.4}, "ramps_30_70": {"max": 0.8}}
    assert not _stale(rep)


def test_an_older_schema_is_still_stale():
    """The original rule must survive the new clauses."""
    rep = {"schema": REPORT_SCHEMA - 1, "de00": {"avg_all": 1.2},
           "grey_balance": {}, "ramps_30_70": {}}
    assert _stale(rep)
