"""The graphs' title is "Trend over time", without "(this printer)" (Knut,
#182 5817448879; register B8-1008).

*"today, the title "Trend over time (this printer)" is shown between the
tab-bar arrows and the right edge of the window. The graphs belong to the
generated report, so "(this printer)" can be removed, giving more space for
the tabs."* The window's title beside the tab bar, the PDF's heading over the
graphs and the welcome window's help that names it all say the same.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_the_window_and_the_pdf_say_trend_over_time(tmp_path, qapp):
    """MUTATION, proved to land: the label built with the old key."""
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, _run, vs = _messy_project(tmp_path, dates=2)
    dlg = mrd.MeasurementReportDialog(s, None,
                                      initial_ti3=vs[-1].measurement_ti3)
    try:
        assert dlg._trend_label.text() == "Trend over time"
        assert "this printer" not in dlg._pdf_html(
            dlg._runs_for_report(), "")
    finally:
        dlg.close()
    import inspect
    import ui.dialogs.welcome_dialog as wd
    assert "(this printer)" not in inspect.getsource(wd)
    assert "(this printer)" not in inspect.getsource(mrd)


def test_german_says_it_without_the_printer():
    import json
    from pathlib import Path
    de = json.loads((Path(__file__).resolve().parents[1] / "data" / "i18n"
                     / "de.json").read_text(encoding="utf-8"))
    assert de["Trend over time"] == "Verlauf über die Zeit"
    assert not any("dieser Drucker" in v for v in de.values()
                   if "Verlauf über die Zeit" in v)
