"""A document called "Colour summary (one page)" must print on one page.

It printed on two. Measured against the PDF's own A4 layout — 15 mm margins, a
34 px header band, a 22 px footer band, the writer at 96 dpi — the body came to
990 px against 952 available: over by 38 px, about 10 mm. Sixteen example
colours in a single column is what did it, and a hand-over page in one tall thin
column wastes its right half anyway.

Eight and eight is 112 px shorter. With that, the same document measures 841 px
against 952, so there are 111 px of headroom, about seven lines: enough for a
run description of ordinary length, and this test is where that margin is kept
honest.

The test lays the document out exactly as `_export_pdf` does. Asserting on the
saved PDF's page objects instead would pass on a file nobody could read.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import workflow.measurement_report as mr

#: What `_export_pdf` sets up, kept here so the test fails if it drifts.
_MARGIN_MM = 15.0
_HEADER_PX = 34.0
_FOOTER_PX = 22.0
_DPI = 96


def _laid_out(dlg, runs):
    """(pages, body height, available height) for the PDF of *runs*."""
    from PyQt6.QtCore import QMarginsF, QSizeF
    from PyQt6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument
    out = Path(tempfile.mkdtemp()) / "x.pdf"
    writer = QPdfWriter(str(out))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(_MARGIN_MM, _MARGIN_MM, _MARGIN_MM,
                                    _MARGIN_MM), QPageLayout.Unit.Millimeter)
    writer.setResolution(_DPI)
    page_w, page_h = float(writer.width()), float(writer.height())
    body_h = page_h - _HEADER_PX - _FOOTER_PX
    doc = QTextDocument()
    doc.setHtml(dlg._report_body_html(runs, for_pdf=True))
    doc.setPageSize(QSizeF(page_w, body_h))
    return doc.pageCount(), doc.size().height(), body_h


def test_it_is_one_page(a_run, qapp):
    dlg, run = a_run
    _set(dlg, run, mr.REPORT_TYPE_SUMMARY)
    pages, used, avail = _laid_out(dlg, dlg._runs_for_document())
    assert pages == 1, f"{used} px of body against {avail} available"


def test_and_keeps_room_for_a_description_of_ordinary_length(a_run, qapp):
    """THE MARGIN IS THE POINT. A document that fits by one pixel is a document
    that stops fitting the next time a sentence is added to it."""
    dlg, run = a_run
    _set(dlg, run, mr.REPORT_TYPE_SUMMARY)
    _, used, avail = _laid_out(dlg, dlg._runs_for_document())
    assert avail - used >= 60, (
        f"only {avail - used:.0f} px spare; the one-page summary is one "
        "sentence away from being two pages")


def test_the_example_colours_are_laid_out_in_blocks_of_eight(a_run, qapp):
    dlg, run = a_run
    _set(dlg, run, mr.REPORT_TYPE_SUMMARY)
    assert dlg._SWATCH_ROWS_PER_COLUMN == 8
    html = dlg._report_body_html(dlg._runs_for_document(), for_pdf=True)
    # Two blocks means the headings appear twice over.
    assert html.count(">Asked for<") >= 3, \
        "sixteen colours in two blocks plus the corners is three headings"


def test_a_short_list_stays_in_one_block(a_run, qapp):
    """Eight cube corners are eight, not four and four."""
    dlg, run = a_run
    one = dlg._swatch_table_html([{"name": str(i), "hex": "#112233"}
                                  for i in range(8)])
    assert one.count(">Asked for<") == 1


def test_a_block_short_of_patches_keeps_the_rows_level(a_run, qapp):
    """Nine patches over two blocks is five and four. The short block must keep
    the shape of its last row, or everything beside it rides up a line."""
    dlg, run = a_run
    two = dlg._swatch_table_html(
        [{"name": str(i), "hex": "#112233"} for i in range(9)], columns=2)
    assert two.count("<tr>") == 1 + 5, "one heading row and five patch rows"
    assert two.count(">Asked for<") == 2
    # The LAST row is the one with a hole in it. Every row of the table must
    # carry the same number of cells, or the block beside the short one rides
    # up a line and the two stop lining up.
    rows = [r for r in two.split("<tr>")[1:] if r.strip()]
    counts = [r.count("<td") for r in rows[1:]]
    assert len(set(counts)) == 1, f"rows carry {sorted(set(counts))} cells"


@pytest.fixture
def a_run(tmp_path, qapp):
    import sys

    from PyQt6.QtCore import QSettings

    from core.file_manager import Project
    from core.settings import AppSettings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from drive_one_page_report import _measurement_ti3

    work = tmp_path / "w"
    work.mkdir()
    st = AppSettings()
    st._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    st.set("custom_output_path", str(work))
    proj = Project.create(work / "G", "G")
    run = proj.current_run()
    run.ensure_dir()
    meta = run.load_meta()
    meta.description = "Hahnemuhle Photo Rag 308, job 4471"
    run.save_meta(meta)
    ti3 = run.dir / "G.ti3"
    _measurement_ti3(ti3)
    dlg = MeasurementReportDialog(st, None, initial_ti3=ti3)
    yield dlg, run
    dlg.close()


def _set(dlg, run, tid: str) -> None:
    from workflow.run_compliance import set_run_report_type
    set_run_report_type(run, tid)
    dlg._forget_limits()
    dlg._sync_limit_controls()
    dlg._refresh()


#: The printable width of the PDF's A4 page at 96 dpi with 15 mm margins, which
#: is what `_export_pdf` sets up. Measured, not assumed: 679 px.
_PAGE_W = 679.0


def _shipped_languages() -> list:
    from pathlib import Path as _P
    d = _P(__file__).resolve().parent.parent / "data" / "i18n"
    return ["en"] + sorted(p.stem for p in d.glob("*.json")
                           if not p.stem.startswith("parameters"))


@pytest.mark.parametrize("code", _shipped_languages())
def test_the_colour_table_fits_across_the_page_in_every_language(code, qapp):
    """TWO BLOCKS SIDE BY SIDE IS A WIDER TABLE, and a heading is a translated
    string. Russian's "Asked for" is nearly twice the English, so the language
    that decides whether this fits is not the one it was designed in. Measured
    across the shipped catalogues: 342 px in Chinese to 538 in Russian, against
    679 of page.
    """
    from PyQt6.QtCore import QSizeF
    from PyQt6.QtGui import QTextDocument

    import core.i18n as i18n
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    before = getattr(i18n, "current_language", lambda: "en")()
    try:
        i18n.set_language(code)
        rows = [{"name": str(i), "expected_hex": "#112233",
                 "hex": "#334455", "de": 1.23} for i in range(16)]
        html = MeasurementReportDialog._swatch_table_html(None, rows, columns=2)
        doc = QTextDocument()
        doc.setHtml(html)
        doc.setPageSize(QSizeF(4000, 4000))
        assert doc.idealWidth() <= _PAGE_W, (
            f"{code}: the example-colour table is {doc.idealWidth():.0f} px "
            f"wide and the page is {_PAGE_W:.0f}")
    finally:
        i18n.set_language(before)
