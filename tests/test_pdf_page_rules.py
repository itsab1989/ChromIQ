"""Knut's ground rules for every PDF ChromIQ writes (#164, 2026-08-23).

    *"All headers must have one free line above itself. No heading shall exist
    on one page while belonging section text is moved to next page. Headers
    should be on same page as its belonging text. Page numbers should be centred
    on page width, not right aligned. … A single row in a table of many rows of
    text must not be allowed to be split across two pages. … If a table of many
    rows is split across pages, then the first row belonging to the same table,
    on any page it is split, should have the header row repeated."*

The rules live in ``ui/pdf_layout.py`` so the Measurement Report and the printed
Help cards obey the same ones. Two traps are worth knowing before changing any
of this, and each has a test here:

* Qt parses a margin in ``px`` and ignores one in ``pt`` — a style sheet written
  in points has no spacing at all, which is what made bullets and dictionary
  entries print as one block.
* A page-break pushed onto EVERY cell of a table row skips a whole page and
  leaves a blank one; it belongs on the first cell alone.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

BODY_H = 700.0


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _doc(html: str, css: str = "", body_h: float = BODY_H):
    from PyQt6.QtCore import QSizeF
    from PyQt6.QtGui import QTextDocument
    d = QTextDocument()
    if css:
        d.setDefaultStyleSheet(css)
    d.setHtml(html)
    d.setPageSize(QSizeF(520.0, body_h))
    return d


def _rows_html(n: int, words: int = 40) -> str:
    filler = " ".join(["lorem"] * words)
    body = "".join(f"<tr><td>row {i}</td><td>{filler}</td></tr>" for i in range(n))
    return ("<body><table cellpadding='4'><tr><th>Key</th><th>What</th></tr>"
            + body + "</table></body>")


# --- the units trap ---------------------------------------------------------

def test_a_margin_in_points_is_silently_ignored(qapp):
    """The measurement behind the rewrite of the print style sheet. If this ever
    starts passing in points, the sheet can be simplified — until then, spacing
    written in pt is spacing that does not exist."""
    doc = _doc("<body><p>one</p><p class='b'>two</p></body>",
               "p.b { margin-top: 40pt; }")
    assert doc.begin().next().blockFormat().topMargin() == 0.0

    doc = _doc("<body><p>one</p><p class='b'>two</p></body>",
               "p.b { margin-top: 40px; }")
    assert doc.begin().next().blockFormat().topMargin() == 40.0


def test_the_print_sheet_spaces_things_in_pixels(qapp):
    """…so the sheet the help cards print with must not use pt for spacing."""
    import re

    from ui.help_card_print import _PRINT_CSS

    # Comments first: the sheet EXPLAINS the trap in prose, and the explanation
    # naturally contains the very thing being warned about.
    css = re.sub(r"/\*.*?\*/", "", _PRINT_CSS, flags=re.S)
    for prop, value, unit in re.findall(
            r"(margin[a-z-]*|padding[a-z-]*)\s*:\s*([^;}]+?)(pt|cm|mm)\b", css):
        raise AssertionError(
            f"{prop} is written in {unit} ({value}{unit}) — Qt ignores it")


# --- repeated header rows ---------------------------------------------------

def test_a_split_table_repeats_its_header_row(qapp):
    from ui.pdf_layout import repeat_table_headers

    doc = _doc(_rows_html(30))
    assert repeat_table_headers(doc) == 1
    table = doc.rootFrame().childFrames()[0]
    assert table.format().headerRowCount() == 1


def test_every_card_table_gets_one(qapp):
    """The cards' HTML uses <th> without <thead>, so every table arrived with a
    header-row count of zero — Qt's repeat-on-each-page needs the count."""
    from ui.dialogs.welcome_dialog import WORKFLOWS
    from ui.help_card_print import build_document
    from ui.pdf_layout import repeat_table_headers

    total = 0
    for wf in WORKFLOWS:
        total += repeat_table_headers(build_document(wf))
    assert total >= 10, f"only {total} tables were given a header row"


# --- whole rows -------------------------------------------------------------

def _split_rows(doc, body_h=BODY_H) -> int:
    from ui.pdf_layout import _first_split_row
    n = 0
    seen = set()
    while True:
        row = _first_split_row(doc, body_h)
        if row is None or (id(row[0]), row[1]) in seen:
            return n
        seen.add((id(row[0]), row[1]))
        n += 1
        break                      # one is enough to fail the assertion
    return n


def _card_doc(key: str):
    """A real help card, laid out on a real A4 body — the geometry these rules
    were written for. Synthetic fixtures kept failing to reproduce a split row
    at all, which is its own lesson: the faults live in the real content."""
    from PyQt6.QtCore import QSizeF

    from ui.dialogs.welcome_dialog import WORKFLOWS
    from ui.help_card_print import build_document, _FOOTER_H, _HEADER_H

    body_h = 267 * 96 / 25.4 - _HEADER_H - _FOOTER_H
    wf = next(w for w in WORKFLOWS if w["key"] == key)
    doc = build_document(wf, width_mm=180.0, height_mm=body_h * 25.4 / 96)
    doc.setPageSize(QSizeF(180 * 96 / 25.4, body_h))
    return doc, body_h


def test_a_table_row_is_never_cut_in_half(qapp):
    """Measured on the real cards: the folder guide and the Main Actions card
    each cut a row in half before this rule was added."""
    from ui.pdf_layout import (_first_split_row, avoid_split_rows,
                               paginate_tables, repeat_table_headers)

    fixed_any = False
    for key in ("file_guide", "main_actions"):
        doc, body_h = _card_doc(key)
        repeat_table_headers(doc)
        paginate_tables(doc, body_h)
        if _first_split_row(doc, body_h) is None:
            continue
        fixed_any = True
        assert avoid_split_rows(doc, body_h) > 0
        assert _first_split_row(doc, body_h) is None, (
            f"{key}: a table row is still split across two pages")
    assert fixed_any, "no card splits a row any more — is the fixture still real?"


def test_pushing_a_row_does_not_leave_a_blank_page(qapp):
    """The break goes on the row's FIRST cell only. On every cell, Qt skips a
    whole page and leaves it empty — measured, and the reason this is a rule
    rather than a loop over cells."""
    from ui.pdf_layout import avoid_split_rows

    doc = _doc(_rows_html(40, words=45), body_h=430.0)
    before = doc.pageCount()
    avoid_split_rows(doc, 430.0)
    after = doc.pageCount()
    assert after <= before + 2, (
        f"pushing rows added {after - before} pages — cells are being broken "
        f"individually")


def test_it_gives_up_on_a_row_taller_than_a_page(qapp):
    """…rather than looping for ever trying to fit it."""
    from ui.pdf_layout import avoid_split_rows

    doc = _doc(_rows_html(3, words=900))
    avoid_split_rows(doc, 200.0)         # must return


# --- headings stay with their text -----------------------------------------

def test_a_heading_is_never_left_alone_at_the_foot_of_a_page(qapp):
    """Also measured on the real cards — the folder guide orphaned two headings
    and the keyboard card one."""
    from ui.pdf_layout import (_first_orphan_heading, avoid_orphan_headings,
                               paginate_tables, repeat_table_headers)

    fixed_any = False
    for key in ("file_guide", "keyboard_shortcuts", "glossary"):
        doc, body_h = _card_doc(key)
        repeat_table_headers(doc)
        paginate_tables(doc, body_h)
        if _first_orphan_heading(doc, body_h) is None:
            continue
        fixed_any = True
        assert avoid_orphan_headings(doc, body_h) > 0
        assert _first_orphan_heading(doc, body_h) is None, (
            f"{key}: a heading is still stranded at the foot of a page")
    assert fixed_any, "no card orphans a heading any more — fixture still real?"


def test_the_dictionary_entries_stay_with_their_definitions(qapp):
    """Knut named this card: *"The header and the description of these terms and
    words should not be separated between two pages."*"""
    from ui.dialogs.welcome_dialog import WORKFLOWS
    from ui.help_card_print import build_document, _FOOTER_H, _HEADER_H
    from ui.pdf_layout import _first_orphan_heading, avoid_orphan_headings

    body_h = 267 * 96 / 25.4 - _HEADER_H - _FOOTER_H
    wf = next(w for w in WORKFLOWS if w.get("kind") == "glossary")
    doc = build_document(wf, width_mm=180.0, height_mm=body_h * 25.4 / 96)
    from PyQt6.QtCore import QSizeF
    doc.setPageSize(QSizeF(180 * 96 / 25.4, body_h))
    avoid_orphan_headings(doc, body_h)
    assert _first_orphan_heading(doc, body_h) is None


# --- the page number --------------------------------------------------------

def test_the_page_number_is_centred(qapp, tmp_path):
    """Qt's own page number is right-aligned and cannot be moved, which is why
    the pages are painted by hand."""
    import numpy as np
    from PyQt6.QtGui import QPdfWriter
    from PyQt6.QtPdf import QPdfDocument
    from PyQt6.QtCore import QMarginsF, QSize
    from PyQt6.QtGui import QPageLayout, QPageSize
    from PIL import Image

    from ui.pdf_layout import render_paged

    out = tmp_path / "numbered.pdf"
    writer = QPdfWriter(str(out))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    writer.setResolution(96)
    doc = _doc("<body>" + "<p>" + " ".join(["lorem"] * 2000) + "</p></body>")
    pages = render_paged(doc, writer, page_w=float(writer.width()),
                         page_h=float(writer.height()),
                         draw_header=lambda *a: None)
    assert pages >= 2

    pdf = QPdfDocument(None)
    pdf.load(str(out))
    img = pdf.render(0, QSize(600, 850))
    img.save(str(tmp_path / "p1.png"))
    # COMPOSITE ONTO WHITE FIRST. A rendered page is RGBA with a transparent
    # background, and `.convert("L")` turns every transparent pixel BLACK — so
    # the whole footer band counted as ink, the "centre" of it was the centre of
    # the page whatever the text did, and this test passed for any alignment at
    # all (mutating AlignHCenter → AlignRight passed all 6851 tests).
    page = Image.open(tmp_path / "p1.png").convert("RGBA")
    flat = Image.alpha_composite(Image.new("RGBA", page.size, (255, 255, 255, 255)),
                                 page)
    arr = np.asarray(flat.convert("L"))
    foot = arr[-60:]                       # the footer band
    cols = np.where((foot < 200).any(axis=0))[0]
    assert len(cols), "no page number was drawn"
    middle = (cols.min() + cols.max()) / 2
    assert abs(middle - arr.shape[1] / 2) < arr.shape[1] * 0.08, (
        f"the page number is centred on {middle:.0f} of {arr.shape[1]} — "
        f"it is not on the page's centre line")

# --- the two faults the beta.2 review found ---------------------------------

def _card_pages_ink(qapp, key: str, tmp_path):
    """Ink coverage of every printed page of a card, as a percentage."""
    import numpy as np
    from PIL import Image
    from PyQt6.QtCore import QMarginsF, QSize
    from PyQt6.QtGui import QPageLayout, QPageSize
    from PyQt6.QtPdf import QPdfDocument
    from PyQt6.QtPrintSupport import QPrinter

    from ui.dialogs.welcome_dialog import WORKFLOWS
    from ui.help_card_print import render_card

    wf = next(w for w in WORKFLOWS if w["key"] == key)
    out = tmp_path / f"{key}.pdf"
    pr = QPrinter(QPrinter.PrinterMode.HighResolution)
    pr.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    pr.setOutputFileName(str(out))
    pr.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    pr.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    render_card(wf, pr)

    doc = QPdfDocument(None)
    doc.load(str(out))
    inks = []
    for i in range(doc.pageCount()):
        f = tmp_path / f"{key}_{i}.png"
        doc.render(i, QSize(600, 850)).save(str(f))
        page = Image.open(f).convert("RGBA")
        flat = Image.alpha_composite(
            Image.new("RGBA", page.size, (255, 255, 255, 255)), page)
        inks.append(float((np.asarray(flat.convert("L")) < 200).mean()) * 100.0)
    return inks


def test_a_heading_is_moved_not_given_a_page_of_its_own(qapp, tmp_path):
    """The orphan rule must not CREATE the fault it exists to prevent.

    `paginate_tables` pushes a table by breaking at the block above it, and
    walks up only one non-empty block to find it — on the keyboard card that was
    the section's intro paragraph, which left the heading behind. Adding a
    second break, on the heading, then gave the heading a page to itself: the
    card went from 2 pages to 3, the new one carrying 0.12 % ink. Worse than
    before the rule existed, and the rule's own test reported success because it
    skips any block that already carries a break.
    """
    inks = _card_pages_ink(qapp, "keyboard_shortcuts", tmp_path)
    assert len(inks) == 2, f"the card should print on 2 pages, got {len(inks)}"
    assert min(inks) > 2.0, (
        f"a page is all but empty — ink per page: "
        f"{[round(v, 2) for v in inks]}")


def test_no_card_prints_an_almost_empty_page(qapp, tmp_path):
    """…and the same for the cards that exercise the rules hardest."""
    for key in ("glossary", "main_actions"):
        inks = _card_pages_ink(qapp, key, tmp_path)
        assert min(inks) > 2.0, (
            f"{key} prints an almost empty page: "
            f"{[round(v, 2) for v in inks]}")
