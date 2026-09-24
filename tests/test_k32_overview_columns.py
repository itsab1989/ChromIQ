"""K32, Knut on beta 41 (#182 5814107188): the Overview of Measurement Metrics
on screen.

*"The on-screen report in the measurement window should show at least 4
columns of included measurements before braking the table and continuing the
table below in a new table, if the report holds more included
measurements."*

Two faults, measured on screen on Report-Limits-Evenness run 1 (four dates):
the window fitted its tables to the PDF's 679 px however wide it was, and the
fit allowed only half a pixel over it while Qt rounds the Metric column's
percentage up, so four dates measured 680 px and came out as two tables of two
in the window AND the PDF.
"""
from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _window(tmp_path, qapp, dates):
    from tests.test_a_generated_report_is_one_document import _messy_project
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _fm, _run, vs = _messy_project(tmp_path, dates=dates)
    dlg = MeasurementReportDialog(s, None, initial_ti3=vs[-1].measurement_ti3)
    dlg.resize(1300, 900)
    dlg.show()
    qapp.processEvents()
    dlg._select_all_btn.click()
    qapp.processEvents()
    return dlg


def _dates_per_table(html: str) -> "list[int]":
    """How many dated columns each metric table of *html* holds."""
    return [t.count("<th align='right'")
            # any width: the window's tables are `_SCREEN_TABLE_WIDTH`, not
            # 100% (challenge 2 of beta 42, #3)
            for t in re.findall(r"<table width='[0-9.]+%' cellpadding='4'.*?</table>",
                                html, flags=re.S)]


def _overview(dlg, *, for_pdf: bool) -> "list[int]":
    runs = dlg._runs_for_document()
    dlg._report_body_html(runs, for_pdf=for_pdf)      # sets the medium
    return _dates_per_table(dlg._comparison_table_html(runs))


def test_each_medium_gets_its_own_width_and_floor(tmp_path, qapp):
    """The window's body is fitted to its own page width with a floor of four
    dates a table; the PDF's to the paper with no floor.

    MUTATIONS, each proved to land: fit the window to the PDF's width again
    (`self._table_width = _PDF_TEXT_W` for both media); drop the floor
    (`_table_min_cols = 1` in the window)."""
    import ui.dialogs.measurement_report_dialog as mrd
    dlg = _window(tmp_path, qapp, 5)
    try:
        runs = dlg._runs_for_document()
        assert len(runs) == 5
        dlg._report_body_html(runs, for_pdf=False)
        assert dlg._table_width == pytest.approx(dlg._screen_table_width())
        assert dlg._table_width > mrd._PDF_TEXT_W, dlg._table_width
        assert dlg._table_min_cols == 4
        dlg._report_body_html(runs, for_pdf=True)
        assert dlg._table_width == mrd._PDF_TEXT_W
        assert dlg._table_min_cols == 1
    finally:
        dlg.close()


def test_a_narrow_window_still_shows_four_dates_a_table(tmp_path, qapp):
    """Where fewer dates would fit, the window still puts four in its first
    table (Knut's floor); the same width without the floor does not.

    MUTATION, proved to land: start the column search at 1 whatever the
    floor (`floor = 1` in `_chunked_metric_tables`)."""
    dlg = _window(tmp_path, qapp, 5)
    try:
        runs = dlg._runs_for_document()
        dlg._report_body_html(runs, for_pdf=False)
        dlg._table_width = 330.0
        window = _dates_per_table(dlg._comparison_table_html(runs))
        # four first, the rest below (not shared out evenly, which gave 3 + 2)
        assert window == [4, 1], window
        dlg._table_min_cols = 1
        paper = _dates_per_table(dlg._comparison_table_html(runs))
        assert paper[0] < 4, paper
    finally:
        dlg.close()


def test_one_pixel_of_rounding_is_not_an_overflow(qapp):
    """Qt rounds the Metric column's percentage share up by a pixel: a table
    whose document measures 680 px at a 679 px text width fits; one of 690
    does not (the document adds its 4 px margin a side to the table).

    MUTATION, proved to land: `_TABLE_FIT_SLACK_PX = 0.5`."""
    import ui.dialogs.measurement_report_dialog as mrd

    def table(w):
        return (f"<table width='{w}' cellpadding='0' cellspacing='0'>"
                "<tr><td>x</td></tr></table>")
    assert mrd._table_fits_the_page(table(672), 679.0)
    assert not mrd._table_fits_the_page(table(682), 679.0)
