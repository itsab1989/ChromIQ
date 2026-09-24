"""The report page is never wider than the view it is shown in (challenge 2
of beta 42, #3; register B8-1003).

Photographed on screen: a horizontal scroll bar under the report page that
moved the page by ONE pixel (`crop-wide-hscroll.png`). Measured on the demo
project: the document was the view's width plus one, at 1234, 1500 and
1700 px and at the window's minimum, because a metric table of width 100% is
laid out one pixel wider than the page (Qt rounds the Metric column's share
up, `_TABLE_FIT_SLACK_PX`). The window's tables are now a little less than
the page (`_SCREEN_TABLE_WIDTH`), which leaves that pixel inside it at every
width and follows a resize; the PDF keeps 100% of the paper. B8-985's rule (at least
four dates a table in the window) is measured by its own tests and is not
touched.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_every_metric_table_fits_the_page_it_is_laid_out_in(qapp):
    """The window's metric table, 1 to 8 dates, laid out in a page of every
    width from 600 to 1800 px (in 7 px steps): never wider than the page.

    MUTATION, proved to land: `_SCREEN_TABLE_WIDTH = "100%"` (217 of the
    1204 tables are one pixel over)."""
    from PyQt6.QtGui import QTextDocument
    import ui.dialogs.measurement_report_dialog as mrd

    class _Page:
        _ZEBRA_BG = "#eeeeee"
        _table_width_attr = mrd._SCREEN_TABLE_WIDTH
    rows = [("Average ΔE00, all patches within gamut",
             [0.52, 0.61, 0.73, 3.1, 1.2, 0.4, 0.9, 1.1]),
            ("Maximum ΔE00, highest 5 %",
             [1.12, 1.27, 6.73, 12.3, 2.2, 0.8, 1.5, 3.3])]
    over = []
    for n in (1, 2, 3, 4, 5, 6, 8):
        dates = [f"2026-10-{i + 1:02d}" for i in range(n)]
        html = mrd.MeasurementReportDialog._metric_table(
            _Page(), dates,
            [(label, [f"<td align='right'>{v:.2f}</td>" for v in vals[:n]])
             for label, vals in rows])
        for w in range(600, 1800, 7):
            doc = QTextDocument()
            doc.setHtml(html)
            doc.setTextWidth(w)
            if doc.size().width() > w:
                over.append((n, w, doc.size().width()))
    assert not over, f"{len(over)} tables wider than their page: {over[:6]}"


def test_the_page_fits_its_view_at_every_width_and_after_a_resize(
        tmp_path, qapp):
    """The same, in a real report window: drawn at each width, and drawn
    wide then narrowed without being drawn again."""
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, _run, vs = _messy_project(tmp_path, dates=3)
    dlg = mrd.MeasurementReportDialog(s, None,
                                      initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        dlg._saved_combo.setCurrentIndex(0)          # New report…
        dlg._saved_combo.activated.emit(0)
        qapp.processEvents()
        assert "<table" in dlg._report_body_html(dlg._runs_for_report(),
                                                 for_pdf=False)
        over = []
        for w in (1700, 1500, 1234, 1100, 1000, 900, 820, 760):
            dlg.resize(w, dlg.height())
            qapp.processEvents()
            dlg._render()
            qapp.processEvents()
            doc = dlg._view.document()
            if doc.size().width() > doc.textWidth():
                over.append(("drawn", w, doc.size().width(), doc.textWidth()))
        # and a page drawn wide, then narrowed without being drawn again
        dlg.resize(1700, dlg.height())
        qapp.processEvents()
        dlg._render()
        for w in (1500, 1100, 820, 760):
            dlg.resize(w, dlg.height())
            qapp.processEvents()
            doc = dlg._view.document()
            if doc.size().width() > doc.textWidth():
                over.append(("resized", w, doc.size().width(),
                             doc.textWidth()))
        assert not over, f"the page is wider than its view: {over}"
    finally:
        dlg.close()


def test_the_pdf_keeps_the_papers_whole_width(tmp_path, qapp):
    """The PDF's tables are the paper's text width, as before."""
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, _run, vs = _messy_project(tmp_path, dates=2)
    dlg = mrd.MeasurementReportDialog(s, None,
                                      initial_ti3=vs[-1].measurement_ti3)
    try:
        pdf = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
        assert "<table width='100%' cellpadding='4'" in pdf
        screen = dlg._report_body_html(dlg._runs_for_report(), for_pdf=False)
        assert f"<table width='{mrd._SCREEN_TABLE_WIDTH}' cellpadding='4'" \
            in screen
    finally:
        dlg.close()
