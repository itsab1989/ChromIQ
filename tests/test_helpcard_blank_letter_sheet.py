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

#: RETIRED AS A GATE (2026-08-26). An ink threshold cannot survive a change of
#: script. Measured over all 13 languages x 21 cards x {A4, Letter} = 1350
#: sheets, rendered through the real `render_card`:
#:
#:   zh_CN/cmyk_n/Letter p2   43 characters of content   0.599 %  — would PASS
#:   nl/cmyk_n/A4        p2   50 characters, same text   0.316 %  — would FAIL
#:
#: The two sheets are visually identical — one line of type plus the colophon.
#: Han glyphs simply carry about twice the ink of Latin ones. The 1350 sheets
#: run 0.18 %…1.1 % with no gap for a threshold to sit in, and the English
#: figure this was calibrated on — `file_guide` A4 p6, called "the sparsest
#: legitimate sheet" — is itself a sheet carrying ONE TABLE ROW.
#:
#: The gate is now structural (below): does a sheet carry the colophon and
#: nothing else? That is the question `drop_orphan_tail` actually answers.
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



def _body_band_text(pdf, printer):
    """The same band as :func:`_body_band_ink`, read as TEXT instead of as ink.

    `y` comes from the FULL matrix. `tm[5]` on its own is meaningless in a
    Qt-written PDF — it runs 0…932 on a 792 pt page, because the CTM carries the
    flip — and reading it raw puts the page number up in the header.
    """
    from pypdf import PdfReader
    from PyQt6.QtGui import QPageLayout

    from ui.help_card_print import _FOOTER_H, _HEADER_H

    mm = QPageLayout.Unit.Millimeter
    paint = printer.pageLayout().paintRect(mm)
    top = paint.y() + _HEADER_H * 25.4 / 96.0
    bot = paint.y() + paint.height() - _FOOTER_H * 25.4 / 96.0
    out = []
    for page in PdfReader(str(pdf)).pages:
        h = float(page.mediabox.height)
        got: list[str] = []

        def visit(t, cm, tm, _fd, _fs, _got=got, _h=h):
            if t and t.strip():
                y = (_h - (cm[1] * tm[4] + cm[3] * tm[5] + cm[5])) * 25.4 / 72.0
                if top - 0.5 <= y <= bot + 0.5:
                    _got.append(t.strip())

        page.extract_text(visitor_text=visit)
        out.append(" ".join(got))
    return out

def test_no_help_card_prints_a_sheet_that_carries_only_the_colophon(qapp, tmp_path):
    """Every card, both papers — the contract `drop_orphan_tail` really holds.

    This is the structural form of the beta.15 defect: a sheet whose body band
    carries the card's colophon and NOTHING else. It replaces an ink threshold
    that flagged a Dutch sheet and passed a visually identical Chinese one (see
    `_MIN_BODY_INK` above).
    """
    from core.version import APP_VERSION
    from ui.dialogs.welcome_dialog import WORKFLOWS

    faults = []
    for wf in WORKFLOWS:
        for size in _SIZES:
            pdf, pages, pr = _print_card(wf["key"], size, tmp_path)
            for i, body in enumerate(_body_band_text(pdf, pr)):
                flat = " ".join(body.split())
                if flat and flat.startswith(f"ChromIQ {APP_VERSION}"):
                    faults.append(
                        f"{wf['key']}/{size} sheet {i + 1} of {pages} carries "
                        f"only the colophon: {flat!r}")
    assert not faults, "\n".join(faults)


def test_the_orphan_rule_is_what_is_saving_those_sheets(qapp, tmp_path,
                                                        monkeypatch):
    """THE CONTROL, and the reason the test above is worth having.

    Without it that assertion holds whether `drop_orphan_tail` works or not —
    which is exactly how a sibling test in this project stayed green for weeks
    while the behaviour it named was broken. Switch the rule off and the wasted
    sheets must come back.
    """
    import ui.pdf_layout as pdf_layout

    from core.version import APP_VERSION

    monkeypatch.setattr(pdf_layout, "drop_orphan_tail", lambda *a, **k: None)
    found = []
    for key in ("first_profile", "cmyk_n", "file_guide"):
        pdf, _pages, pr = _print_card(key, "Letter", tmp_path)
        for body in _body_band_text(pdf, pr):
            if " ".join(body.split()).startswith(f"ChromIQ {APP_VERSION}"):
                found.append(key)
    assert sorted(found) == ["cmyk_n", "file_guide", "first_profile"], (
        "disabling drop_orphan_tail did not bring the three beta.15 sheets "
        f"back, so the test above is measuring nothing: {found}")


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
