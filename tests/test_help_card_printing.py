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
    ("A4", "landscape", 15),
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


def test_the_page_size_comes_from_the_printer(qapp):
    """`print_card` must ASK the printer, not assume A4 — that assumption is
    what made this an A4-only fix the first time round."""
    import inspect

    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize
    from PyQt6.QtPrintSupport import QPrinter

    from ui import help_card_print

    src = inspect.getsource(help_card_print.print_card)
    assert "printable_size_mm" in src, "print_card never asks the printer"

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
