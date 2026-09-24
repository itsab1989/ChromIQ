"""B8-928 (beta 40): Report Scope counts dated verifications as measurements.

Second check R3 of beta 39 (``~/Desktop/ChromIQ-beta39-proof/second-check-R3/
rerun/en-all/pdfs/I4-iso-12647-8-en/page-01.png``): three dates of ONE
profile run were listed as "Report-Limits-Every-Limit-Set-verify, Instrument:
X-Rite ColorMunki · 3 verification runs", while the list header ("2
Messungen" / "2 measurements") and the running header of the same report
count measurements. There was one profile run; a dated verification is one
measurement of it.

MUTATION, proven red: put the ``verification`` branch of `_count_label` in
`MeasurementReportDialog._scope_html` back ("verification run(s)").
"""
from __future__ import annotations

import re

import pytest

from tests.test_the_one_page_summary_is_about_one_sheet import (  # noqa: F401
    two_dated)

pytestmark = pytest.mark.usefixtures("qapp")


def _text(html: str) -> str:
    return " ".join(re.sub("<[^>]+>", " ", html).split())


def test_two_dates_of_one_run_are_two_measurements(two_dated):
    dlg, _older, _newer = two_dated
    # one chart, as for dates of one run (the fixture names them apart)
    runs = [dict(r, chart="Two-verify") for r in dlg._history]
    assert len(runs) == 2, "both dates are loaded"
    assert dlg._report_kind(runs) == "verification"
    txt = _text(dlg._scope_html(runs))
    assert "· 2 measurements" in txt, txt
    assert "verification runs" not in txt.replace(
        "The following verification runs are included:", ""), txt


def test_one_date_is_one_measurement(two_dated):
    dlg, _older, _newer = two_dated
    txt = _text(dlg._scope_html(list(dlg._history)[:1]))
    assert "· 1 measurement" in txt and "· 1 measurements" not in txt, txt


def test_the_german_words_are_the_list_headers_own():
    """No new text: the words are the ones the list header already uses,
    translated by hand."""
    import json
    from pathlib import Path
    de = json.loads((Path(__file__).resolve().parent.parent / "data" / "i18n"
                     / "de.json").read_text(encoding="utf-8"))
    assert de["measurement"] == "Messung"
    assert de["measurements"] == "Messungen"
