"""Every Help card can be printed — or saved as a PDF from the print dialog.

#164, Knut, 2026-08-23: *"That it would be possible to print a currently viewed
help card via normal print dialog (which also would allow saving as pdf). This
would make it easier for a user to have something in their hand while working,
for example printing the keyboard shortcuts."*

The trap this file guards is that "the card on screen" is four different shapes,
and only one of them is already HTML. A print path built for that one would have
silently produced an empty page for the glossary, dropped the workflow diagram,
and printed nothing at all for the step-list cards — the majority of them.
"""
from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _cards():
    from ui.dialogs.welcome_dialog import WORKFLOWS
    return list(WORKFLOWS)


def _text_of(doc) -> str:
    return doc.toPlainText()


@pytest.mark.parametrize("wf", _cards(), ids=lambda w: w["key"])
def test_every_card_prints_something_real(qapp, wf):
    """No card may come out as a title over an empty page."""
    from ui.help_card_print import build_document

    doc = build_document(wf)
    text = _text_of(doc)
    assert wf["title"] in text, f"{wf['key']}: the title is missing"
    # The title and the footer are always there; the body has to add to them.
    body = text.replace(wf["title"], "").replace(wf["subtitle"], "")
    assert len(body.strip()) > 120, (
        f"{wf['key']}: printed page has no body ({len(body.strip())} chars)")


def test_the_glossary_prints_its_terms(qapp):
    from ui.dialogs.welcome_dialog import GLOSSARY
    from ui.help_card_print import build_document

    wf = next(w for w in _cards() if w.get("kind") == "glossary")
    text = _text_of(build_document(wf))
    for term, _definition in GLOSSARY[:8]:
        assert term in text, f"the glossary printed without {term!r}"


def test_a_step_card_prints_its_steps_with_the_tab_named(qapp):
    """On screen a step carries a coloured tab badge. Paper has no tabs to point
    at, so the tab is named instead."""
    from ui.help_card_print import build_document

    wf = next(w for w in _cards() if w.get("steps"))
    text = _text_of(build_document(wf))
    for step in wf["steps"][:3]:
        assert step[1][:40] in text, "a step went missing from the printout"
    assert any(name in text for name in
               ("Create Chart", "Measure", "Build Profile", "Check & Refine")), (
        "no step says which tab it happens in")


def test_the_shortcuts_card_prints_its_keys(qapp):
    from ui.help_card_print import build_document

    wf = next(w for w in _cards() if w.get("kind") == "shortcuts")
    text = _text_of(build_document(wf))
    assert len(text) > 400, "the shortcuts table printed nearly empty"


def test_the_getting_started_card_keeps_its_diagram(qapp):
    """A workflow card without its workflow picture is not the card the user was
    reading — and the diagram lives in a painted widget, in no HTML at all."""
    from ui.help_card_print import build_document, card_html
    from PyQt6.QtGui import QTextDocument

    wf = next(w for w in _cards() if w.get("kind") == "getting_started")
    doc = QTextDocument()
    markup = card_html(wf, doc)
    assert "<img" in markup, "the diagram was dropped from the printed card"
    assert doc.resource(QTextDocument.ResourceType.ImageResource,
                        _first_img_src(markup)) is not None, (
        "the <img> points at a resource the document does not carry")
    assert len(_text_of(build_document(wf))) > 500


def _first_img_src(markup: str):
    from PyQt6.QtCore import QUrl
    m = re.search(r'<img src="([^"]+)"', markup)
    return QUrl(m.group(1)) if m else QUrl()


def test_the_page_is_printed_black_on_white(qapp):
    """The dialog is themed; the paper is not. A dark-theme card sent straight
    to a printer is a solid black sheet."""
    from ui.help_card_print import _PRINT_CSS

    assert "color: #000000" in _PRINT_CSS
    assert "background: #1" not in _PRINT_CSS


def test_the_button_only_shows_on_a_card(qapp, tmp_path):
    """There is nothing to print while the menu of cards is showing."""
    from PyQt6.QtCore import QSettings

    from core.settings import AppSettings
    from ui.dialogs.welcome_dialog import WelcomeDialog

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    dlg = WelcomeDialog(s)
    # OPEN A CARD, THEN GO BACK. Two things this test got wrong at first:
    # `isVisible()` is False for every child of a dialog that was never shown,
    # so the negative half could not fail; and the button starts hidden from its
    # constructor, so asserting before any navigation never exercises the
    # handler that is supposed to hide it. Both together let a build with the
    # button forced permanently visible pass. Going Back is the real journey and
    # it runs the handler in both directions.
    dlg._on_card_clicked(_cards()[0]["key"])
    assert dlg._print_btn.isVisibleTo(dlg), "no way to print the card on screen"
    assert dlg._current_card_key == _cards()[0]["key"]
    dlg._stack.setCurrentIndex(0)          # ← Back
    assert not dlg._print_btn.isVisibleTo(dlg), (
        "the Print button offers to print the menu of cards")


def test_printing_declines_cleanly_when_the_dialog_is_dismissed(qapp, tmp_path,
                                                               monkeypatch):
    """Cancelling the print dialog must not raise, and must not print."""
    from PyQt6.QtCore import QSettings

    from core.settings import AppSettings
    from ui import help_card_print
    from ui.dialogs.welcome_dialog import WelcomeDialog

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    dlg = WelcomeDialog(s)
    dlg._on_card_clicked(_cards()[0]["key"])
    monkeypatch.setattr(help_card_print, "_exec_print_dialog", lambda d: False)
    dlg._print_current_card()          # must not raise


def test_the_dialog_call_is_one_stubbable_line():
    """A native print dialog in a headless run blocks for ever, so the suite has
    to be able to replace exactly one thing (tests/conftest.py does)."""
    import inspect

    from ui import help_card_print

    src = inspect.getsource(help_card_print.print_card)
    assert "_exec_print_dialog" in src
    assert ".exec()" not in src, "print_card opens the modal itself"


# --- the page is not always A4 ---------------------------------------------

def _image_draws(pdf_bytes: bytes) -> int:
    """How many times the document draws an image XObject."""
    import re
    import zlib
    total = 0
    for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.S):
        try:
            content = zlib.decompress(stream)
        except zlib.error:
            continue
        total += len(re.findall(rb"/Im\d+\s+Do", content))
    return total


@pytest.mark.parametrize("page,orientation,margin_mm", [
    ("A4", "portrait", 15),
    ("Letter", "portrait", 15),
    ("A5", "portrait", 15),
    ("A6", "portrait", 15),
    ("A4", "portrait", 45),
    ("A4", "portrait", 0),
])
def test_the_diagram_is_whole_on_any_page(qapp, tmp_path, page, orientation,
                                          margin_mm):
    """The workflow picture must land ONCE, entire, whatever paper is chosen.

    It was placed at a fixed size, so on A4 it lost its whole right-hand column
    off the page edge and printed again on the next sheet. Solving it against
    the real printer fixed A4 — and A5 and A6 went straight back to splitting,
    because a picture placed part-way down a page has to fit what is LEFT of
    that page. It takes both a height ceiling and a page break in front of it,
    and this test is why we know that: with either one removed, at least one of
    these page sizes fails.
    """
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize
    from PyQt6.QtPrintSupport import QPrinter

    from ui.help_card_print import build_document, printable_size_mm

    wf = next(w for w in _cards() if w.get("kind") == "getting_started")
    out = tmp_path / f"{page}_{orientation}_{margin_mm}.pdf"
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(out))
    printer.setPageSize(QPageSize(getattr(QPageSize.PageSizeId, page)))
    printer.setPageOrientation(
        QPageLayout.Orientation.Landscape if orientation == "landscape"
        else QPageLayout.Orientation.Portrait)
    printer.setPageMargins(QMarginsF(*([margin_mm] * 4)),
                           QPageLayout.Unit.Millimeter)

    w_mm, h_mm = printable_size_mm(printer)
    build_document(wf, width_mm=w_mm, height_mm=h_mm).print(printer)

    draws = _image_draws(out.read_bytes())
    assert draws == 1, (
        f"{page} {orientation} @{margin_mm}mm: the diagram was drawn {draws} "
        f"times — it is being split across pages again")


def test_landscape_fits_the_width_and_may_run_on(qapp, tmp_path):
    """Knut's own ruling for the one case that cannot have both.

    *"If the page printed or saved as pdf is landscape, then image width must
    still be adapted, but it should be ok to let the drawing image overflow to
    the next page, as the image is tall and would become too small if whole
    image height would be adapted to landscape page height."*
    """
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize
    from PyQt6.QtPrintSupport import QPrinter

    from ui.help_card_print import printable_size_mm, render_card

    wf = next(w for w in _cards() if w.get("kind") == "getting_started")
    out = tmp_path / "landscape.pdf"
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(out))
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageOrientation(QPageLayout.Orientation.Landscape)
    printer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    render_card(wf, printer)

    w_mm, _h_mm = printable_size_mm(printer)
    from PyQt6.QtGui import QTextDocument

    from ui.help_card_print import card_html
    doc = QTextDocument()
    markup = card_html(wf, doc, width_mm=w_mm, height_mm=120.0)
    m = re.search(r'<img[^>]*width="(\d+)"', markup)
    assert m, "no diagram in the landscape card"
    shown_mm = int(m.group(1)) * 25.4 / 96.0
    assert shown_mm > w_mm * 0.95, (
        f"landscape shrank the drawing to {shown_mm:.0f} mm on a "
        f"{w_mm:.0f} mm page instead of fitting the width")
    assert _image_draws(out.read_bytes()) >= 1


def test_the_page_size_comes_from_the_printer(qapp):
    """`print_card` must ASK the printer, not assume A4 — that assumption is
    what made this an A4-only fix the first time round."""
    import inspect

    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize
    from PyQt6.QtPrintSupport import QPrinter

    from ui import help_card_print

    src = inspect.getsource(help_card_print.render_card)
    assert "printable_size_mm" in src, "the card is not measured against the device"

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A5))
    printer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Unit.Millimeter)
    w_mm, h_mm = help_card_print.printable_size_mm(printer)
    # A5 is 148 x 210 mm, less 10 mm on each side.
    assert 125 < w_mm < 132 and 187 < h_mm < 194, (
        f"A5 with 10 mm margins measured as {w_mm:.0f} x {h_mm:.0f} mm")


def test_a_missing_print_module_is_not_mistaken_for_a_cancel(qapp, tmp_path,
                                                             monkeypatch):
    """`print_card` returning False means "the user cancelled", and the caller
    stays quiet on it. A missing QtPrintSupport must raise instead, or a broken
    install looks exactly like a deliberate Cancel."""
    import inspect

    from ui import help_card_print

    src = inspect.getsource(help_card_print.print_card)
    body = src.split("except ImportError", 1)
    assert len(body) == 2, "the ImportError branch is gone"
    assert "raise" in body[1].split("printer =")[0], (
        "a missing QtPrintSupport still returns False, which reads as a cancel")


# ---------------------------------------------------------------------------
# A REAL PRINTER, NOT A PDF WRITER
# ---------------------------------------------------------------------------
# Everything above prints through `setOutputFormat(PdfFormat)`, and that engine
# does whatever `setResolution` asks. A printer does not: `QMacPrintEngine`
# snaps the request to the queue's own `supportedResolutions()`. beta.2 asked
# for 96 dpi, silently got 300, went on dividing `width()` by 96, and laid every
# card out for a 562 mm page — printing it at 32 % of its size into the top
# third of the sheet. A green suite and a full visual proof sheet both missed
# it, because both were PDF. `QPrintPreviewWidget` drives the native engine
# without a printer attached, and reports the same metrics a print job sees.


def _native_printer(page_size, margin_mm=15.0):
    """A printer on the real print engine — or a skip.

    WITH NO PRINT QUEUE INSTALLED A `QPrinter` QUIETLY BECOMES A PDF WRITER,
    and a PDF writer accepts `setResolution(96)`. Both sides of the comparison
    below then collapse onto the same engine and the test passes against the
    very bug it was written for — measured: the two page-count tests pass
    unmodified against beta.2 on a machine with no printers. So say "not
    proven here" rather than "green" (#164 review).
    """
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize
    from PyQt6.QtPrintSupport import QPrinter

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    if printer.outputFormat() != QPrinter.OutputFormat.NativeFormat:
        pytest.skip("no print queue on this machine: QPrinter fell back to PDF")
    printer.setPageSize(QPageSize(page_size))
    printer.setPageMargins(QMarginsF(margin_mm, margin_mm, margin_mm, margin_mm),
                           QPageLayout.Unit.Millimeter)
    return printer


def _native_render(qapp, wf, printer):
    """Paint *wf* through the native engine; return (pages, geometry).

    *geometry* is what the card was laid out to and what the painter was scaled
    by — the two numbers the whole fix turns on.
    """
    from PyQt6.QtPrintSupport import QPrintPreviewWidget

    from ui import help_card_print

    seen = {}
    real = help_card_print.render_paged

    def spy(doc, device, **kw):
        seen["page_w"] = kw["page_w"]
        seen["page_h"] = kw["page_h"]
        seen["scale"] = kw.get("scale", 1.0)
        seen["dev_w"], seen["dev_h"] = device.width(), device.height()
        return real(doc, device, **kw)

    help_card_print.render_paged = spy
    try:
        widget = QPrintPreviewWidget(printer)
        widget.paintRequested.connect(
            lambda dev: seen.__setitem__("pages", render_card_via(wf, dev)))
        widget.updatePreview()
        qapp.processEvents()
    finally:
        help_card_print.render_paged = real
    return seen


def render_card_via(wf, dev):
    from ui.help_card_print import render_card
    return render_card(wf, dev)


def _native_page_count(qapp, wf, page_size, margin_mm=15.0):
    """Page count for *wf* through the NATIVE print engine."""
    printer = _native_printer(page_size, margin_mm)
    seen = _native_render(qapp, wf, printer)
    return seen.get("pages"), printer


def _pdf_page_count(wf, page_size, tmp_path, margin_mm=15.0):
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize
    from PyQt6.QtPrintSupport import QPrinter

    from ui.help_card_print import render_card

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(tmp_path / "card.pdf"))
    printer.setPageSize(QPageSize(page_size))
    printer.setPageMargins(QMarginsF(margin_mm, margin_mm, margin_mm, margin_mm),
                           QPageLayout.Unit.Millimeter)
    return render_card(wf, printer)


@pytest.mark.parametrize("page,name", [("A4", "A4"), ("Letter", "Letter")])
def test_a_real_printer_gets_the_same_pages_as_the_pdf(qapp, tmp_path, page, name):
    """Every card, on both common paper sizes, through both engines.

    If these ever disagree the card is being laid out for one page size and
    painted onto another — which is exactly what beta.2 shipped.
    """
    from PyQt6.QtGui import QPageSize

    from ui.dialogs.welcome_dialog import WORKFLOWS

    size = getattr(QPageSize.PageSizeId, page)
    wrong = []
    for wf in WORKFLOWS:
        native, _ = _native_page_count(qapp, wf, size)
        pdf = _pdf_page_count(wf, size, tmp_path)
        if native != pdf:
            wrong.append(f"{wf['key']}: printer {native} pages, PDF {pdf}")
    assert not wrong, f"{name}: " + "; ".join(wrong)


def test_the_card_is_laid_out_to_exactly_the_page_it_is_painted_on(qapp):
    """THE ONE NUMBER THE WHOLE FIX TURNS ON.

    The document is laid out in 96-dpi pixels and the painter is scaled to the
    device. Those two have to agree: ``page_w * scale`` must be the device's
    own width, or the card is drawn for one page and painted onto another.
    beta.2 got this wrong in the small direction — 96/300, a third of the size.
    Nothing in the suite could see it, because page COUNT does not change when
    a painter is scaled; this watches the geometry instead.
    """
    from PyQt6.QtGui import QPageSize

    from ui.dialogs.welcome_dialog import WORKFLOWS

    for page in ("A4", "Letter", "A5"):
        printer = _native_printer(getattr(QPageSize.PageSizeId, page))
        seen = _native_render(qapp, WORKFLOWS[0], printer)
        assert seen, f"{page}: the card was never painted"
        for axis in ("w", "h"):
            want = seen[f"dev_{axis}"]
            got = seen[f"page_{axis}"] * seen["scale"]
            # A page is thousands of device pixels; a millimetre is the bar.
            tol = max(4.0, want / 254.0)
            assert abs(got - want) <= tol, (
                f"{page} {axis}: laid out for {got:.0f} device px, painted onto "
                f"{want} (page_{axis}={seen[f'page_{axis}']:.1f} @ 96 dpi, "
                f"scale={seen['scale']:.3f})")


def test_a4_is_measured_as_a4_and_not_as_something_three_times_wider(qapp):
    """The number that gave the fault away: A4 less 15 mm margins is 180 mm of
    printable width. beta.2 read it as 562."""
    from PyQt6.QtGui import QPageSize

    from ui.dialogs.welcome_dialog import WORKFLOWS

    printer = _native_printer(QPageSize.PageSizeId.A4)
    seen = _native_render(qapp, WORKFLOWS[0], printer)
    w_mm = seen["page_w"] * 25.4 / 96.0
    h_mm = seen["page_h"] * 25.4 / 96.0
    assert abs(w_mm - 180.0) < 1.0, f"A4 laid out to {w_mm:.1f} mm wide"
    assert abs(h_mm - 267.0) < 1.0, f"A4 laid out to {h_mm:.1f} mm tall"


def test_printing_does_not_downgrade_the_printer(qapp):
    """`render_card` must not write to the device it is handed.

    beta.2's `setResolution(96)` left the caller's printer at 300 dpi — a
    printer the user had told the system to run at 600. Painting a document is
    not the moment to change the job's settings.
    """
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize
    from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewWidget

    from ui.dialogs.welcome_dialog import WORKFLOWS
    from ui.help_card_print import render_card

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    seen = {}

    def paint(dev):
        seen["before"] = dev.resolution()
        render_card(WORKFLOWS[0], dev)
        seen["after"] = dev.resolution()

    widget = QPrintPreviewWidget(printer)
    widget.paintRequested.connect(paint)
    widget.updatePreview()
    qapp.processEvents()
    assert seen["after"] == seen["before"], (
        f"painting moved the job from {seen['before']} dpi to {seen['after']}")


def test_the_print_button_opens_the_system_dialog_and_no_window_of_ours(qapp):
    """Basti, #164: "the preview you introduced completely messes up the page
    layout and i want to have it gone". The system's own print window is what
    opens — Qt's `QPrintPreviewDialog` is not to come back.

    macOS cannot show a preview pane inside that window through Qt at all: the
    pane is drawn by an `NSPrintOperation` asking a real `NSView` for its pages,
    and Qt presents a bare `NSPrintPanel`. Windows' common print dialog has no
    preview, and Qt hides the one in its own Linux dialog. "Save as PDF…" is
    the route to seeing the pages first, on every platform.
    """
    import inspect

    from ui import help_card_print

    src = inspect.getsource(help_card_print.print_card)
    assert "QPrintPreviewDialog" not in src, (
        "the Qt preview window is back; Basti asked for it to be gone")
    assert "QPrintDialog" in src, "the system print dialog is not being opened"


def test_a_device_that_will_not_say_its_size_still_gets_a_whole_page(qapp,
                                                                     tmp_path):
    """The fallback in `printable_size_mm` decides the printed geometry now
    that the function is on the live path, and it used to return the BODY
    height (225 mm) where a PAGE height (267 mm) was wanted — 60 mm blank at
    the foot of every sheet, with the page number floating above the paper
    edge (#164 review)."""
    from ui.help_card_print import _FALLBACK_PAGE_MM, _FOOTER_H, _HEADER_H
    from ui.help_card_print import printable_size_mm

    class WontSay:
        def pageLayout(self):
            raise RuntimeError("no page layout")

    w_mm, h_mm = printable_size_mm(WontSay())
    assert (w_mm, h_mm) == _FALLBACK_PAGE_MM
    # A4 less the 15 mm margins ChromIQ asks for, which is the page it sets up.
    assert abs(w_mm - 180.0) < 0.5 and abs(h_mm - 267.0) < 0.5, (
        f"the fallback page is {w_mm:.0f} x {h_mm:.0f} mm")
    # …and it is a PAGE, not the body band inside it.
    assert h_mm * 96.0 / 25.4 > _HEADER_H + _FOOTER_H + 700, (
        "the fallback is the body height again, not the page height")


def test_accepting_the_dialog_actually_prints(qapp, monkeypatch):
    """The line the revert put back — `render_card(wf, printer)` — was reached
    by no test at all, because `tests/conftest.py` stubs every print dialog to
    Cancel for the whole suite. So Print… could have quietly printed nothing
    and the gate would still have been green (#164 review)."""
    from ui import help_card_print
    from ui.dialogs.welcome_dialog import WORKFLOWS

    printed = []
    monkeypatch.setattr(help_card_print, "_exec_print_dialog", lambda d: True)
    monkeypatch.setattr(help_card_print, "render_card",
                        lambda wf, dev, **kw: printed.append((wf["key"], dev)))
    assert help_card_print.print_card(WORKFLOWS[0]) is True
    assert len(printed) == 1, "the dialog was accepted and nothing was printed"
    assert printed[0][0] == WORKFLOWS[0]["key"]

    printed.clear()
    monkeypatch.setattr(help_card_print, "_exec_print_dialog", lambda d: False)
    assert help_card_print.print_card(WORKFLOWS[0]) is False
    assert not printed, "Cancel printed anyway"
