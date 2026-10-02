"""#182 A1 (Knut, 2026-10-02, 5943085974): *"'Save report as PDF' should not
be allowed to be pressed if the report area is empty (no report loaded)."*

The button follows the PAGE, through the window's own doors: greyed while
the report area shows no report (the window opened with nothing measured,
an error page, the empty page a door draws after a kept page), live from
the moment a report is drawn, and still live over a page that is KEPT after
Clear List (Knut, 2026-09-18: greyed only *"if no report is loaded in the
window at all"*).

MUTATIONS, each proved red (L_impl_knut_rulings/MUTATIONS.md):
* `_sync_pdf_button` always enabling the button;
* `_show_no_report` leaving `_page_drawn` as it was;
* `_render` not marking a drawn report (`_page_drawn = True` dropped).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from tests.test_import_measurement_module import (_PATCHES, _cgats,  # noqa: E402
                                                  _env)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _window(s, ti3, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    qapp.processEvents()
    return dlg


def _measured_elsewhere(tmp_path):
    p = tmp_path / "elsewhere.ti3"
    p.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    return p


def test_an_empty_window_offers_no_pdf_until_a_report_is_drawn(
        tmp_path, qapp, monkeypatch):
    import ui.dialogs.measurement_report_dialog as MRD
    s, fm, _ctl = _env(tmp_path)
    run1 = fm.project().run("run1")          # nothing measured
    dlg = _window(s, run1.measurement_ti3, qapp)
    try:
        assert not dlg._sources
        assert not dlg._pdf_btn.isEnabled(), (
            "Save report as PDF is live over an empty report area")
        # Add Profile's Measurements…, through its own file dialog
        extra = _measured_elsewhere(tmp_path)
        monkeypatch.setattr(MRD, "open_files_dialog",
                            lambda *a, **k: [str(extra)])
        dlg._on_add_project()
        qapp.processEvents()
        assert dlg._sources, "nothing was added"
        assert "Report Scope" in dlg._view.toPlainText()
        assert dlg._pdf_btn.isEnabled(), "a report is drawn, no PDF offered"
    finally:
        dlg.close()


def test_a_kept_page_keeps_the_pdf_and_the_empty_page_after_it_does_not(
        tmp_path, qapp):
    s, fm, _ctl = _env(tmp_path)
    run1 = fm.project().run("run1")
    run1.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    dlg = _window(s, run1.measurement_ti3, qapp)
    try:
        assert dlg._pdf_btn.isEnabled()
        dlg._on_clear_list()                 # the page is kept
        qapp.processEvents()
        assert "Report Scope" in dlg._view.toPlainText()
        assert dlg._pdf_btn.isEnabled(), "the kept report lost its PDF"
        # a door that must replace the page (a delete that took the report
        # shown) draws the empty page: no report, no PDF
        dlg._start_new_report()
        qapp.processEvents()
        assert "Report Scope" not in dlg._view.toPlainText()
        assert not dlg._pdf_btn.isEnabled(), (
            "Save report as PDF is live over the empty page")
    finally:
        dlg.close()


def test_an_error_page_is_not_a_report(tmp_path, qapp, monkeypatch):
    """Add Profile's Measurements… with a file that cannot be read puts the
    error page where the report was; 4.3.2 left the PDF live over it
    (the list still held measurements)."""
    import ui.dialogs.measurement_report_dialog as MRD
    s, fm, _ctl = _env(tmp_path)
    run1 = fm.project().run("run1")
    run1.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    dlg = _window(s, run1.measurement_ti3, qapp)
    try:
        assert dlg._pdf_btn.isEnabled()
        bad = tmp_path / "broken.cxf"
        bad.write_text("not a measurement", encoding="utf-8")
        monkeypatch.setattr(MRD, "open_files_dialog",
                            lambda *a, **k: [str(bad)])
        dlg._on_add_project()
        qapp.processEvents()
        assert "Report Scope" not in dlg._view.toPlainText(), (
            "the error page did not replace the report; the test proves "
            "nothing")
        assert dlg._sources
        assert not dlg._pdf_btn.isEnabled(), (
            "Save report as PDF is live over an error page")
    finally:
        dlg.close()
