"""The Report Results table fits across the saved PDF's page (beta 37, H1).

Round B before beta 37 photographed it cut off at the right margin: the
Threshold series' eleven dates lost three verdict columns off the paper
(en-Threshold-full-p4.png), four German dates lost "(empfohlen)" and the last
digit of a date (de-Even-full-p4.png), and English broke "(recommende/d)"
mid-word (en-Even-full-p4.png). Six columns a table was a count chosen for
English with short labels, and the Metric column never wrapped.

Laid out the way `_export_pdf` lays the document out: the report's own font,
at the PDF's text width of 679 px (A4 less 15 mm a side, at 96 dpi).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from PyQt6.QtCore import QSizeF
from PyQt6.QtGui import QTextDocument


def _languages() -> list:
    d = Path(__file__).resolve().parent.parent / "data" / "i18n"
    return ["en"] + sorted(p.stem for p in d.glob("*.json")
                           if not p.stem.startswith("parameters"))


def _tables(n_runs: int) -> "list[str]":
    """The results tables for *n_runs* dated columns carrying the longest
    labels and cells the report prints."""
    from core.i18n import tr
    from workflow.compliance_sets import ROWS
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog as D
    stub = SimpleNamespace(_ZEBRA_BG="#eeeeee")
    stub._metric_table = lambda dates, rows: D._metric_table(stub, dates, rows)
    runs = [{"created": f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}T10:00:00"}
            for i in range(n_runs)]
    judged = (tr("ChromIQ default (recommended)") + " " + tr("(edited)"))
    word = ("<td align='center' style='font-weight:bold'>PASS"
            "<sup style='font-weight:normal'>&nbsp;2) 3)</sup></td>")
    getters = [(tr(row.label), (lambda r: word)) for row in ROWS]
    getters.append((tr("Overall"), lambda r: word))
    getters.append((tr("Judged against"),
                    lambda r: ("<td align='center' style='font-size:10px'>"
                               + judged + "</td>")))
    html = D._chunked_metric_tables(stub, runs, getters)
    return [t + "</table>" for t in html.split("</table>") if t.strip()]


def _laid_out(table_html: str) -> QTextDocument:
    from PyQt6.QtWidgets import QApplication
    family = QApplication.font().family().replace("'", "")
    doc = QTextDocument()
    doc.setHtml(f"<div style=\"font-family:'{family}';font-size:12px\">"
                + table_html + "</div>")
    doc.setPageSize(QSizeF(679.0, 100_000))
    return doc


@pytest.mark.parametrize("code", _languages())
@pytest.mark.parametrize("n_runs", [4, 11])
def test_every_results_table_fits_the_page_with_no_word_broken(code, n_runs,
                                                               qapp):
    """MUTATION (proved 2026-09-23): replace the fit test in
    `_chunked_metric_tables`, `if all(_table_fits_the_page(t) ...)`, with
    `if True:` so the first chunking of six is taken unmeasured, and 18 of
    the 28 cases go red, English and German among them, on the width and on
    a word broken across lines. (Putting `white-space:nowrap` back on the
    Metric cells alone does NOT go red: the measuring loop then simply
    chooses fewer columns, which is the point of measuring.)"""
    import core.i18n as i18n
    from ui.dialogs.measurement_report_dialog import _words_broken_across_lines
    before = getattr(i18n, "current_language", lambda: "en")()
    try:
        i18n.set_language(code)
        tables = _tables(n_runs)
        assert tables
        columns = 0
        for t in tables:
            doc = _laid_out(t)
            assert doc.size().width() <= 679.5, (
                f"{code}, {n_runs} dates: a results table is "
                f"{doc.size().width():.0f} px wide on a 679 px page")
            broken = _words_broken_across_lines(doc)
            assert not broken, f"{code}: a word is broken in {broken[0]!r}"
            columns += t.count("<th align='right'")
        assert columns == n_runs, "every date is in some table"
    finally:
        i18n.set_language(before)


def test_the_dates_are_shared_out_evenly(qapp):
    """Eleven dates in tables of six, six, and a stub of one, or in tables of
    four, four and three: the second."""
    tables = _tables(11)
    counts = [t.count("<th align='right'") for t in tables]
    assert max(counts) - min(counts) <= 1, counts


def test_the_width_the_tables_are_fitted_to_is_the_pdfs(qapp, tmp_path):
    """The constant is the writer's own text width, floored."""
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize, QPdfWriter
    from ui.dialogs.measurement_report_dialog import _PDF_TEXT_W
    w = QPdfWriter(str(tmp_path / "x.pdf"))
    w.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    w.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    w.setResolution(96)
    assert _PDF_TEXT_W <= float(w.width()) < _PDF_TEXT_W + 2
