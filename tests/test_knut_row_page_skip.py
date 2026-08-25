"""Knut, 4.1.3-beta.13: a straddling table row is moved TWO pages, not one.

    *"instead of closing that row and starting a new one on page 1, it stretches
    the row to the next page (page 2), then through the whole page 2, and then
    starts the next row in the table perfectly at the top of the page on page 3
    … How is it possible to not understand that the top of row 7, with its
    header, shall start at the top of page 2?"*

Three assertions, each of which fails on 4.1.3-beta.14.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

_TABLE_CARDS = ("main_actions", "file_guide")
_SIZES = ("A4", "Letter")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _laid_out_card(key: str, size: str):
    """The card's document, with every page rule applied, exactly as printed."""
    from PyQt6.QtCore import QMarginsF, QSizeF
    from PyQt6.QtGui import QPageLayout, QPageSize, QPdfWriter

    from ui.dialogs.welcome_dialog import WORKFLOWS
    from ui.help_card_print import (_FOOTER_H, _HEADER_H, build_document,
                                    printable_size_mm)
    from ui.pdf_layout import (avoid_orphan_headings, avoid_split_rows,
                               paginate_tables, repeat_table_headers)

    wf = next(w for w in WORKFLOWS if w["key"] == key)
    writer = QPdfWriter(os.devnull)
    writer.setPageSize(QPageSize(getattr(QPageSize.PageSizeId, size)))
    writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    w_mm, h_mm = printable_size_mm(writer)
    page_w = w_mm * 96.0 / 25.4
    body_h = h_mm * 96.0 / 25.4 - _HEADER_H - _FOOTER_H
    doc = build_document(wf, width_mm=w_mm, height_mm=body_h * 25.4 / 96.0)
    doc.setPageSize(QSizeF(page_w, body_h))
    repeat_table_headers(doc)
    paginate_tables(doc, body_h)
    avoid_split_rows(doc, body_h)
    avoid_orphan_headings(doc, body_h)
    return doc, page_w, body_h


def _tables(doc):
    from PyQt6.QtGui import QTextTable
    out, stack = [], [doc.rootFrame()]
    while stack:
        for ch in stack.pop().childFrames():
            stack.append(ch)
            if isinstance(ch, QTextTable):
                out.append(ch)
    out.sort(key=lambda t: t.firstPosition())
    return out


# --- 1. the row must land on the VERY NEXT page ----------------------------

def test_a_moved_row_starts_on_the_page_right_after_the_row_above(qapp):
    """Knut's sentence, as arithmetic.

    A row that will not fit is moved down. It may be moved by ONE page. Moving
    it by two is what leaves a sheet carrying nothing but the repeated header —
    and Qt does exactly that when the break is put on every cell of the row:
    `layoutTable` drops the row one page (qtextdocumentlayout.cpp:2755) and the
    still-set `PageBreak_AlwaysBefore` fires again inside the cell (:3275),
    unconditionally, from the row's new page.
    """
    from ui.pdf_layout import _row_extent, settled_layout

    faults = []
    for key in _TABLE_CARDS:
        for size in _SIZES:
            doc, _page_w, body_h = _laid_out_card(key, size)
            lay = settled_layout(doc)
            for ti, table in enumerate(_tables(doc)):
                prev_end = None
                for r in range(table.rows()):
                    top, bottom = _row_extent(lay, table, r)
                    if not (top or bottom):
                        continue
                    start = int(top // body_h)
                    if prev_end is not None and start - prev_end > 1:
                        faults.append(
                            f"{key}/{size} table {ti} row {r}: the row above "
                            f"ends on page {prev_end + 1} and this row starts "
                            f"on page {start + 1} — {start - prev_end - 1} "
                            f"sheet(s) in between")
                    prev_end = int((bottom - 1) // body_h)
    assert not faults, "\n".join(faults)


# --- 2. no printed sheet may carry only the repeated header ----------------

def _page_rules(img, scale):
    """The y of every full-width horizontal cell border on one rendered page,
    and whether anything below the second one is text."""
    import numpy as np
    w, h = img.width(), img.height()
    ptr = img.bits()
    ptr.setsize(img.sizeInBytes())
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
        h, img.bytesPerLine() // 4, 4)[:, :w, :3]
    ink = arr.mean(axis=2) < 200
    per = ink.sum(axis=1)
    if per.max() == 0:
        return [], False
    wide = per > 0.85 * per.max()
    groups = []
    for y in range(h):
        if wide[y]:
            if groups and y - groups[-1][-1] <= 2:
                groups[-1].append(y)
            else:
                groups.append([y])
    if len(groups) < 2:
        return [g[0] / scale for g in groups], False
    seg = ink[groups[1][-1] + 1:]
    if seg.shape[0] < 4:
        return [g[0] / scale for g in groups], False
    col = seg.sum(axis=0)
    vertical = col >= seg.shape[0] * 0.8       # the table's own side borders
    return [g[0] / scale for g in groups], bool(seg[:, ~vertical].sum())


def _rendered_pages(doc, page_w, body_h, scale=2.0):
    from PyQt6.QtCore import QRectF, Qt
    from PyQt6.QtGui import QAbstractTextDocumentLayout, QImage, QPainter

    from ui.pdf_layout import settled_layout
    lay = settled_layout(doc)
    for pg in range(max(1, doc.pageCount())):
        img = QImage(int(page_w * scale), int(body_h * scale),
                     QImage.Format.Format_RGB32)
        img.fill(Qt.GlobalColor.white)
        p = QPainter(img)
        p.scale(scale, scale)
        p.setClipRect(QRectF(0, 0, page_w, body_h))
        p.translate(0.0, -pg * body_h)
        ctx = QAbstractTextDocumentLayout.PaintContext()
        ctx.clip = QRectF(0, pg * body_h, page_w, body_h)
        lay.draw(p, ctx)
        p.end()
        yield pg, img


def test_no_sheet_carries_only_a_repeated_table_header(qapp):
    """Measured on the paper, not in the model.

    A page that a table continues onto shows the table's top border, the
    repeated header's bottom border, and then at least one row of TEXT. A page
    with those two rules and no text below them is a wasted sheet — the one
    Knut printed twice.
    """
    faults = []
    for key in _TABLE_CARDS:
        for size in _SIZES:
            doc, page_w, body_h = _laid_out_card(key, size)
            for pg, img in _rendered_pages(doc, page_w, body_h):
                rules, has_text = _page_rules(img, 2.0)
                if len(rules) == 2 and not has_text:
                    faults.append(
                        f"{key}/{size} page {pg + 1}: the repeated table header "
                        f"and nothing else")
    assert not faults, "\n".join(faults)


# --- 3. and the #164 defect must not come back -----------------------------

def test_no_empty_band_is_left_under_a_repeated_header(qapp):
    """The regression this rule caused in 4.1.3-beta.2, kept measured.

    Ending the page INSIDE the row above leaves that row's padding and bottom
    border to be painted overleaf: a thin empty strip between the repeated
    header and the first real row. It is invisible to `_row_extent`, which
    measures the text blocks and not the row, so it has to be counted in pixels.
    """
    import numpy as np
    faults = []
    for key in _TABLE_CARDS:
        for size in _SIZES:
            doc, page_w, body_h = _laid_out_card(key, size)
            for pg, img in _rendered_pages(doc, page_w, body_h, scale=4.0):
                w, h = img.width(), img.height()
                ptr = img.bits()
                ptr.setsize(img.sizeInBytes())
                arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
                    h, img.bytesPerLine() // 4, 4)[:, :w, :3]
                ink = arr.mean(axis=2) < 200
                per = ink.sum(axis=1)
                if per.max() == 0:
                    continue
                wide = per > 0.85 * per.max()
                groups = []
                for y in range(h):
                    if wide[y]:
                        if groups and y - groups[-1][-1] <= 2:
                            groups[-1].append(y)
                        else:
                            groups.append([y])
                for a, b in zip(groups, groups[1:]):
                    y0, y1 = a[-1] + 1, b[0]
                    if y1 - y0 < 2:
                        continue
                    seg = ink[y0:y1]
                    col = seg.sum(axis=0)
                    vertical = col >= (y1 - y0) * 0.8
                    if seg[:, ~vertical].sum() == 0:
                        faults.append(
                            f"{key}/{size} page {pg + 1}: an empty {(y1-y0)/4.0:.0f} px "
                            f"band between two cell borders at y={a[0]/4.0:.0f} "
                            f"and y={b[0]/4.0:.0f}")
    assert not faults, "\n".join(faults)
