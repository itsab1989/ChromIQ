"""B8-1342: a report of raw checks said it covered "0 of the 9 measurements"
of its project.

The Report Scope coverage sentence left raw checks out of what the document
covers, from when raw sheets were drawn apart from the report's columns.
Since K51 and K59 they are ordinary columns with their own verdict word, so a
document of raw checks covered, by that count, nothing. Every measurement in
the document is covered by it.

MUTATION, proven red: put `not _is_raw_drift(r)` back into the second
`covered` count of `MeasurementReportDialog._scope_html`.
"""
from __future__ import annotations

import re

import pytest

from tests.test_the_one_page_summary_is_about_one_sheet import (  # noqa: F401
    two_dated)

pytestmark = pytest.mark.usefixtures("qapp")


def _text(html: str) -> str:
    return " ".join(re.sub("<[^>]+>", " ", html).split())


def _raw(r: dict) -> dict:
    return dict(r, is_verification=True, reference_source="design",
                printing=dict(r.get("printing") or {}, colour="raw"))


def test_a_raw_check_in_the_document_is_covered_by_it(two_dated):
    from workflow.measurement_report import is_drift_check
    dlg, _older, _newer = two_dated
    runs = [_raw(r) for r in dlg._history][:1]
    assert is_drift_check(runs[0]), "the fixture must really be a raw check"
    txt = _text(dlg._scope_html(runs))
    assert "covers 0 of" not in txt, txt
    assert "covers 1 of the 2" in txt, txt


def test_every_raw_check_of_the_run_leaves_nothing_uncovered(two_dated):
    dlg, _older, _newer = two_dated
    runs = [_raw(r) for r in dlg._history]
    txt = _text(dlg._scope_html(runs))
    assert "covers 0 of" not in txt and "covers 2 of the 2" not in txt, txt
