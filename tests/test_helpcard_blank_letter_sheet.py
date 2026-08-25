"""Three help cards printed a sheet with nothing on it — on US Letter only.

    `first_profile` 2 pages where A4 takes 1, `cmyk_n` 2 where A4 takes 1,
    `file_guide` 10 where A4 takes 9. Each extra sheet carried the running
    header, the centred page number, and the card's colophon — the
    `<p class="foot">` line "ChromIQ <version> — <title>" — and nothing else.

US Letter's body is **66.5 px shorter than A4's** (886.614 vs 953.134, at the
96 dpi the card is laid out in), so a card that just fits on A4 pushes its last
line over. The colophon needs 34 px — a 14 px line box under a 20 px top margin
— and **shrinking that margin does not help**: at 20, 12, 6 and 0 px the three
cards still print 2, 2 and 10 sheets, because the line box alone overflows by
1.4, 8.4 and 1.7 px.

Two of the three assertions below fail on 4.1.3-beta.15.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

_SIZES = ("A4", "Letter")

#: The lowest body-band ink of any legitimate sheet, measured across all 21
#: cards at both sizes: `file_guide` A4 page 6, at **0.96 %** — the genuinely
#: sparse sheet a row taller than the space left leaves behind. The three
#: wasted sheets measure 0.088 %, 0.106 % and 0.116 %. Half a percent sits a
#: factor of five clear of both.
_MIN_BODY_INK = 0.5


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _print_card(key: str, size: str, tmp_path):
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize
    from PyQt6.QtPrintSupport import QPrinter

    from ui.dialogs.welcome_dialog import WORKFLOWS
    from ui.help_card_print import render_card

    wf = next(w for w in WORKFLOWS if w["key"] == key)
    out = tmp_path / f"{key}_{size}.pdf"
    pr = QPrinter(QPrinter.PrinterMode.HighResolution)
    pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    pr.setOutputFileName(str(out))
    pr.setPageSize(QPageSize(getattr(QPageSize.PageSizeId, size)))
    pr.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    pages = render_card(wf, pr)
    return out, pages, pr


def _body_band_ink(pdf, printer, tmp_path):
    """Ink %, per page, of the BAND BETWEEN OUR OWN HEADER AND FOOTER.

    Whole-page ink cannot see this fault: the wordmark, the spectrum bar and
    the page number are drawn on every sheet, wasted or not. Only the body band
    says whether anything was printed.

    THE PAGE MUST BE COMPOSITED ONTO WHITE FIRST. `QPdfDocument.render` returns
    a transparent background, and a straight conversion to greyscale makes
    every un-inked pixel BLACK — which reports a wasted sheet as 100 % ink.
    """
    import numpy as np
    from PIL import Image
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QPageLayout
    from PyQt6.QtPdf import QPdfDocument

    from ui.help_card_print import _FOOTER_H, _HEADER_H

    mm = QPageLayout.Unit.Millimeter
    paint = printer.pageLayout().paintRect(mm)
    full_h = printer.pageLayout().fullRect(mm).height()
    top_mm = paint.y() + _HEADER_H * 25.4 / 96.0
    bot_mm = paint.y() + paint.height() - _FOOTER_H * 25.4 / 96.0

    doc = QPdfDocument(None)
    doc.load(str(pdf))
    out = []
    for i in range(doc.pageCount()):
        f = tmp_path / f"{pdf.stem}_{i}.png"
        doc.render(i, QSize(600, 850)).save(str(f))
        flat = Image.alpha_composite(
            Image.new("RGBA", (600, 850), (255, 255, 255, 255)),
            Image.open(f).convert("RGBA"))
        arr = np.asarray(flat.convert("L")) < 200
        y0, y1 = int(850 * top_mm / full_h), int(850 * bot_mm / full_h)
        out.append(float(arr[y0:y1].mean()) * 100.0)
    doc.close()
    return out


def test_no_help_card_prints_a_sheet_with_nothing_on_it(qapp, tmp_path):
    """Every card, both papers. FAILS on beta.15 with three named sheets."""
    from ui.dialogs.welcome_dialog import WORKFLOWS

    faults = []
    for wf in WORKFLOWS:
        for size in _SIZES:
            pdf, pages, pr = _print_card(wf["key"], size, tmp_path)
            for i, ink in enumerate(_body_band_ink(pdf, pr, tmp_path)):
                if ink < _MIN_BODY_INK:
                    faults.append(
                        f"{wf['key']}/{size} sheet {i + 1} of {pages}: "
                        f"{ink:.3f} % ink below the running header")
    assert not faults, "\n".join(faults)


@pytest.mark.parametrize("key,pages", [
    ("first_profile", 1), ("cmyk_n", 1), ("file_guide", 9),
])
def test_us_letter_costs_no_more_sheets_than_a4(qapp, tmp_path, key, pages):
    """US Letter's shorter body must not buy a sheet for one grey line.

    beta.15 prints 2, 2 and 10. A4 has always printed 1, 1 and 9.
    """
    for size in _SIZES:
        _pdf, got, _pr = _print_card(key, size, tmp_path)
        assert got == pages, f"{key} on {size}: {got} sheets, expected {pages}"


def test_the_colophon_is_still_printed_once(qapp, tmp_path):
    """…and is not simply thrown away to save the sheet.

    Passes before and after; it is the guard on the fix, not on the fault.
    """
    pypdf = pytest.importorskip("pypdf")
    from core.version import APP_VERSION

    for key in ("first_profile", "cmyk_n", "file_guide"):
        for size in _SIZES:
            pdf, _pages, _pr = _print_card(key, size, tmp_path)
            text = pypdf.PdfReader(str(pdf)).pages[-1].extract_text()
            flat = " ".join(text.split())
            assert f"ChromIQ {APP_VERSION}" in flat, (
                f"{key}/{size}: the colophon is missing from the last sheet")
