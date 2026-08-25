"""Shared page-layout rules for the PDFs ChromIQ produces.

The Measurement Report solved most of this first; #164 asked for the same rules
on printed Help cards, so the machinery lives here and both use it rather than
one copying the other.

Knut's ground rules, 2026-08-23:

    *"All headers must have one free line above itself. No heading shall exist
    on one page while belonging section text is moved to next page. Page numbers
    should be centred on page width, not right aligned. … A single row in a table
    of many rows of text must not be allowed to be split across two pages. … If
    a table of many rows is split across pages, then the first row … should have
    the header row repeated before the table rows continue on a new page."*

Four of those are enforced here — :func:`paginate_tables`,
:func:`avoid_split_rows`, :func:`avoid_orphan_headings` and
:func:`repeat_table_headers` — and the fifth (the free line above a heading) is
a matter of the caller's style sheet, with one trap worth stating loudly:

**Qt's rich-text engine parses a margin in `px` and `em` and silently ignores
one in `pt`, `cm` or `mm`.** A style sheet written in points therefore has no
spacing at all. Measured: `margin-top: 40px` → 40 px, `2em` → 30 px,
`40pt` → 0, `1cm` → 0.

**Why the pages are painted by hand.** ``QTextDocument.print()`` can only put
its page number at the right, and cannot draw anything else — no wordmark, no
colour line. :func:`render_paged` does what the report has always done: give the
document a page the size of the BODY, then paint each page slice with a header
and a centred footer of our own.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, QSizeF, Qt
from PyQt6.QtGui import (QAbstractTextDocumentLayout, QColor, QFont,
                         QFontMetricsF, QPainter, QTextCursor, QTextFormat,
                         QTextTable, QTextTableCellFormat)

from core.i18n import tr
from ui.styles import TAB_COLORS

#: The masthead's own colours for "Chrom" and the "IQ".
WORDMARK_INK = "#1c1b18"
WORDMARK_ACCENT = "#ff4573"


# ---------------------------------------------------------------------------
# The layout every rule below measures
# ---------------------------------------------------------------------------
def settled_layout(doc):
    """The document's layout, with the layout FINISHED — ask for it here.

    **A ``QTextDocument`` lays itself out lazily, and CHANGING one that is only
    half laid out destroys the geometry of everything below the change.** Not
    "makes it stale": destroys it. Every rule in this module measures the
    layout and then edits a block format, so every one of them can trip it, and
    the result is not a bad page break — it is content that never reaches the
    paper at all.

    Measured on the dictionary card, A4 with 15 mm margins (2026-08-24):

    ==================================================  ================
    what was done to the document                       document height
    ==================================================  ================
    laid out, untouched                                 6543 px (7 pages)
    ``blockBoundingRect`` walk, then ONE page break      2939 px (4 pages)
    ``documentSize()`` first, then the same page break   6560 px (7 pages)
    ==================================================  ================

    In the 2939 px case every ``<dd>`` below the change had collapsed to zero
    height, ``pageCount()`` agreed with the wreck, and :func:`render_paged`
    painted the four pages it was told to: **50 of the card's 79 dictionary
    entries were missing from the PDF**, and the last sheet carried the words
    "White point" and nothing else.

    Why: walking blocks with ``blockBoundingRect`` lays the document out only
    as far as the block asked for, so the walk finishes with a layout still in
    progress. Editing then re-lays out from the edit downwards, over a tail
    that was never finished. ``documentSize()`` completes a layout that is
    merely unfinished — which is why asking for it BEFORE the edit is a fix —
    but it does not repair one that has already been ruined, so asking for it
    afterwards is not. Only ``markContentsDirty`` over the whole document does
    that, at the price of a full re-layout.

    So: **settle first, then measure, then change.** Every function here takes
    its layout from this one call, and none takes it from
    ``doc.documentLayout()`` directly.

    NOT THE PAINT DEVICE. That was the first suspicion, and it is wrong: the
    layout's ``paintDevice()`` is ``None`` before, during and after painting,
    and the document's height is identical either side of ``QPainter(device)``
    (measured on the same card, 1200 dpi ``QPdfWriter``).
    """
    lay = doc.documentLayout()
    lay.documentSize()          # finishes a layout that is still in progress
    return lay


# ---------------------------------------------------------------------------
# Pagination rules
# ---------------------------------------------------------------------------
def paginate_tables(doc, body_h: float) -> None:
    """Keep whole tables on one page (Knut #PDF4), heading included.

    Qt ignores CSS page-break-inside, but honours a frame's page-break policy,
    so each table straddling a page boundary is nudged onto the next page
    (topmost first, re-laying-out until none split). A pushed table must take
    its heading along — breaking only the table left "Worst patches" alone at
    the bottom of one page with its rows on the next (Sebastian, 2026-08-10) —
    so the break goes on the single non-empty block sitting directly above the
    table when that block would otherwise stay behind; if the straddle
    survives the next pass, the table itself gets the break too. Tables taller
    than a page can't be helped and are left to :func:`avoid_split_rows`.
    """
    always = QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore

    def _straddling_tables():
        lay = settled_layout(doc)
        found = []
        stack = [doc.rootFrame()]
        while stack:
            for ch in stack.pop().childFrames():
                stack.append(ch)
                if isinstance(ch, QTextTable):
                    r = lay.frameBoundingRect(ch)
                    if (r.height() < body_h - 1
                            and int(r.top() // body_h)
                            != int((r.bottom() - 1) // body_h)):
                        found.append((r.top(), ch))
        found.sort(key=lambda t: t[0])
        return [t for _, t in found]

    def _push_to_next_page(table) -> None:
        lay = settled_layout(doc)
        block = doc.findBlock(table.firstPosition() - 1)
        # The spacer lines of the gap batch (2026-08-13) are whitespace-only
        # blocks sitting between a heading and its table; without skipping
        # them the "take the heading along" rule below would see only the
        # spacer and leave the heading behind — the exact orphan this
        # function exists to prevent. Walk up past pure-whitespace blocks;
        # the same_page/close checks still decide whether what we find is
        # really attached.
        while (block.isValid() and not block.text().strip()
               and doc.findBlock(block.position() - 1).isValid()):
            prev = doc.findBlock(block.position() - 1)
            if prev == block:
                break
            block = prev
        # Never a block inside another table: two stacked tables are joined
        # by an empty separator, and walking past it must not split the
        # table above — fall through to breaking this table instead.
        if block.isValid() and QTextCursor(block).currentTable() is not None:
            block = doc.findBlock(-1)             # invalid → fallback below
        if block.isValid() and block.text().strip():
            t_top = lay.frameBoundingRect(table).top()
            b_rect = lay.blockBoundingRect(block)
            same_page = int(b_rect.top() // body_h) == int(t_top // body_h)
            close = t_top - b_rect.bottom() < 24
            if same_page and close \
                    and not block.blockFormat().pageBreakPolicy() & always:
                bf = block.blockFormat()
                bf.setPageBreakPolicy(always)
                cur = QTextCursor(block)
                cur.setBlockFormat(bf)
                return
        fmt = table.frameFormat()
        fmt.setPageBreakPolicy(always)
        table.setFrameFormat(fmt)

    for _ in range(400):
        straddlers = _straddling_tables()
        if not straddlers:
            break
        _push_to_next_page(straddlers[0])


def repeat_table_headers(doc) -> int:
    """Make every table repeat its first row at the top of each page it spans.

    Knut: *"the first row belonging to the same table, on any page it is split
    … should have the header row repeated before the table rows continue."*
    Qt does this by itself once a table declares how many header rows it has;
    the cards' HTML uses ``<tr>`` with ``<th>`` cells but no ``<thead>``, so
    every table arrived with a header-row count of zero. Returns how many
    tables were given one, so a caller can assert it did something.
    """
    settled_layout(doc)          # never edit a half-laid-out document
    changed = 0
    stack = [doc.rootFrame()]
    while stack:
        for ch in stack.pop().childFrames():
            stack.append(ch)
            if isinstance(ch, QTextTable) and ch.rows() > 1:
                fmt = ch.format()
                if fmt.headerRowCount() < 1:
                    fmt.setHeaderRowCount(1)
                    ch.setFormat(fmt)
                    changed += 1
    return changed


def avoid_split_rows(doc, body_h: float, limit: int = 200) -> int:
    """Never cut a table row in half at a page break (Knut).

    Qt splits a row whenever ANY of it fits the space left on the page — it
    only moves a row down when nothing fits at all. So a straddling row is
    pushed by hand, and HOW it is pushed was measured on the real cards rather
    than assumed:

    * "break before" on the row's first cell alone does nothing;
    * **"break before" on EVERY cell of the row** is what ships. It moves the
      row whole, so nothing of it is left on the previous page;
    * "break after" on the row above looks cheaper and is not. It ends the page
      INSIDE the row above, which leaves that row's padding and bottom border
      to be painted overleaf — a thin empty line under the repeated header
      (Knut, #164). Measured in pixels across all 18 cards at A4 and US Letter:
      break-after leaves 6 such bands, break-before leaves none, and the price
      is 42 → 47 pages on A4 and 46 → 49 on Letter, all of it on the two cards
      with very tall rows.

    WITH ONE EXCEPTION, AND IT IS AN EXPENSIVE ONE. Never break after a row
    :func:`repeat_table_headers` has made a repeating header: Qt then has to
    put the header on the new page too, and the arithmetic runs away. Measured
    on the folder guide on US Letter, one such break cost THREE pages — this
    rule alone took the card from 10 pages to 13, and printed it finished at 14
    where A4 took 9. When the only thing above the straddling row is that
    header, the whole table moves to the next page instead: 11 printed pages on
    Letter, A4 unchanged at 9, and no row left split on any card at either
    size.

    Rows taller than a page cannot be helped, and neither can a table with
    nothing at all in front of it — those fall back to breaking the row itself.
    Returns the number of rows moved.
    """
    after = QTextFormat.PageBreakFlag.PageBreak_AlwaysAfter
    before = QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore
    moved = 0
    tried: set = set()
    for _ in range(limit):
        row = _first_split_row(doc, body_h, skip=tried)
        if row is None:
            return moved
        table, index = row
        # KEYED ON THE TABLE'S POSITION, NOT `id(table)`. PyQt6 does not keep
        # the wrapper alive between walks, so ids get recycled: a row could be
        # retried, or a different table's row silently skipped.
        tried.add((table.firstPosition(), index))
        if index > table.format().headerRowCount() and index > 0:
            # BREAK AFTER THE ROW ABOVE, WITH ITS CELL PADDING ZEROED.
            #
            # QT HONOURS `PageBreak_AlwaysBefore` ON A CELL BLOCK TWICE, so a
            # row marked that way lands TWO pages on, always — which is the
            # blank sheet Knut reported. In qtbase 6.8 `layoutTable` reads
            # `flowPosition(cell.begin())`, already pushed a page down, and
            # drops the row a page; on the relayout the same flag fires again
            # inside the cell, through a `newPage()` that never checks whether
            # the row is already at the top of a page. The row above is then
            # stretched to the page bottom, which is the artefact you SEE, but
            # it is a consequence and not the cause: a sweep with that row
            # ending anywhere from 79 to 409 px of a 400 px page produces the
            # blank sheet identically every time.
            #
            # Breaking AFTER the row above ends the page at the last block
            # inside it, which is honoured once. On its own that leaves the
            # row's padding and bottom border to be painted overleaf — the thin
            # empty band of #164, which is why break-after was abandoned the
            # first time. Zeroing that row's top and bottom cell padding is
            # what removes it: the overshoot past the page boundary is exactly
            # `pageTopMargin + bottomPadding`, and both terms read the cell's
            # own padding property. Measured in pixels at 4x across all 18
            # cards at A4 and US Letter: zero bands, where the naive
            # break-after leaves bands of 12, 12, 7 and 8 px.
            #
            # The whole cost of Knut's "never cut a row" guarantee is 2 sheets
            # across 36 renders (89 pages against 87 with the rules off), not
            # the 10 the previous note claimed. That figure was the price of
            # triggering this Qt bug, not the price of keeping rows whole —
            # and it had been written into three tests as a fact.
            for col in range(table.columns()):
                cell = table.cellAt(index - 1, col)
                blk = cell.lastCursorPosition().block()
                if not blk.isValid():
                    continue
                cf = QTextTableCellFormat(cell.format().toTableCellFormat())
                cf.setTopPadding(0.0)
                cf.setBottomPadding(0.0)
                cell.setFormat(cf)
                fmt = blk.blockFormat()
                if fmt.pageBreakPolicy() & after:
                    continue
                fmt.setPageBreakPolicy(after)
                QTextCursor(blk).setBlockFormat(fmt)
            moved += 1
            continue
        else:                      # only the repeated header sits above it
            block = doc.findBlock(table.firstPosition() - 1)
            policy = before
            # THE BLOCK IN FRONT OF A TABLE CAN BE INSIDE ANOTHER ONE.
            # `paginate_tables` guards the same lookup; this branch was written
            # without it, and on a table nested in a cell the break landed
            # inside the OUTER table and did nothing useful. ChromIQ's own
            # cards never nest, but this module is shared.
            if block.isValid() and QTextCursor(block).currentTable() is not None:
                block = doc.findBlock(-1)                # invalid → fall through
            if not block.isValid():            # the table opens the document
                block = table.cellAt(index, 0).firstCursorPosition().block()
                for col in range(1, table.columns()):
                    other = table.cellAt(index, col).firstCursorPosition().block()
                    fmt = other.blockFormat()
                    fmt.setPageBreakPolicy(before)
                    QTextCursor(other).setBlockFormat(fmt)
        if not block.isValid() or block.blockFormat().pageBreakPolicy() & policy:
            continue          # already pushed and still split — leave it, move on
        cur = QTextCursor(block)
        bf = block.blockFormat()
        bf.setPageBreakPolicy(policy)
        cur.setBlockFormat(bf)
        moved += 1
    return moved


def _first_split_row(doc, body_h: float, skip: "set | None" = None):
    """The topmost ``(table, row_index)`` whose row crosses a page boundary.

    *skip* holds rows a caller has already dealt with, so one stubborn row —
    a header row Qt repeats, or one that still will not fit — does not stop the
    rest of the table from being tidied.
    """
    lay = settled_layout(doc)
    best = None
    stack = [doc.rootFrame()]
    while stack:
        for ch in stack.pop().childFrames():
            stack.append(ch)
            if not isinstance(ch, QTextTable):
                continue
            for r in range(ch.rows()):
                if skip and (ch.firstPosition(), r) in skip:
                    continue
                top, bottom = _row_extent(lay, ch, r)
                if bottom - top >= body_h - 1:
                    continue                  # taller than a page: hopeless
                if int(top // body_h) != int((bottom - 1) // body_h):
                    if best is None or top < best[0]:
                        best = (top, ch, r)
                    break
    return (best[1], best[2]) if best else None


def _row_extent(lay, table, row: int) -> "tuple[float, float]":
    """Top and bottom of one table row, in document coordinates."""
    top, bottom = None, None
    for col in range(table.columns()):
        cell = table.cellAt(row, col)
        block = cell.firstCursorPosition().block()
        last = cell.lastCursorPosition().block()
        if not block.isValid():
            continue
        r1 = lay.blockBoundingRect(block)
        r2 = lay.blockBoundingRect(last)
        top = r1.top() if top is None else min(top, r1.top())
        bottom = r2.bottom() if bottom is None else max(bottom, r2.bottom())
    return (top or 0.0), (bottom or 0.0)


def avoid_orphan_headings(doc, body_h: float, limit: int = 200) -> int:
    """Never leave a heading alone at the foot of a page (Knut).

    A heading is any block whose whole text is bold — which covers the section
    headings of the folder guide, the ``<dt>`` of every dictionary entry, and
    anything else written the same way — and it is an orphan when the block
    that follows it starts on the next page. The heading is then pushed down to
    join it. Returns how many were moved.
    """
    always = QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore
    moved = 0
    tried: set = set()
    for _ in range(limit):
        found = _first_orphan_heading(doc, body_h, skip=tried)
        if found is None:
            return moved
        block, nxt = found
        tried.add(block.position())
        if block.blockFormat().pageBreakPolicy() & always:
            # SKIP IT AND CARRY ON — this used to `return`, which abandoned
            # every LATER orphan in the document because of one heading that
            # would not move. `avoid_split_rows` has always done it this way.
            # A BACKSTOP, NOT A PATH ANYTHING TAKES: `tried` means each heading
            # is looked at once, so nothing reaches this line on any of the 18
            # cards at A4, US Letter or A5 (counted, 2026-08-24). It is here so
            # that a document which does reach it loses one heading rather than
            # all of them.
            continue
        # MOVE THE BREAK, DO NOT ADD ONE.
        #
        # `paginate_tables` pushes a table by breaking at the block ABOVE it,
        # and it walks up only one non-empty block to find it — so on the
        # keyboard card it broke at the section's intro paragraph and left the
        # heading behind. Setting a second break, on the heading, then gave the
        # heading a page to itself: two consecutive forced breaks, 0.12 % ink on
        # the sheet, and a card that printed WORSE than it did before the rule
        # existed. Taking the break off the text and putting it on the heading
        # keeps them together on one page, which is the whole point.
        # …AND ANY BREAK BETWEEN THE TWO, NOT ONLY ONE ON THE FOLLOWER ITSELF.
        # `avoid_split_rows` moves a table by breaking at "the block in front of
        # it", and the block in front of a table is the EMPTY spacer line the
        # HTML leaves there — never the follower this rule is looking at. So the
        # break was invisible here, the heading stayed where it was, and the
        # folder guide printed "Verification runs — checking a finished profile
        # over time" at the foot of a US Letter page with its table overleaf.
        # Walk the whitespace blocks the orphan search stepped over and take the
        # break off those too.
        walk = block.next()
        while walk.isValid():
            if walk.blockFormat().pageBreakPolicy() & always:
                wfmt = walk.blockFormat()
                wfmt.setPageBreakPolicy(QTextFormat.PageBreakFlag.PageBreak_Auto)
                QTextCursor(walk).setBlockFormat(wfmt)
            if walk == nxt:
                break
            walk = walk.next()
        cur = QTextCursor(block)
        bf = block.blockFormat()
        bf.setPageBreakPolicy(always)
        cur.setBlockFormat(bf)
        moved += 1
    return moved


def _is_heading(block) -> bool:
    text = block.text().strip()
    if not text:
        return False
    it = block.begin()
    while not it.atEnd():
        frag = it.fragment()
        if frag.isValid() and frag.text().strip():
            if not frag.charFormat().font().bold():
                return False
        it += 1
    return True


def _line_page(lay, block, body_h: float) -> int:
    """The page the block's FIRST LINE of text lands on.

    NOT the page its box starts on, which is what this used to ask. When a
    block begins in the last few pixels of a page, Qt puts the top of its box
    there and pushes the first line over to the next page. Judged by the box,
    a heading and its definition looked like they were on the same page and the
    rule did nothing — while the sheet showed the bold term alone at the foot
    with its text overleaf. That is exactly Knut's "Instrument" (#164, A5).

    Read off the printed sheets rather than off this arithmetic, judging by the
    box strands "Chart recipe" and "Preset" on A4, "Fiducial marks" and "Patch
    set" on US Letter and three more terms on A5; judging by the first line
    strands none of them at any of the three sizes (2026-08-24). Only the
    dictionary card is affected, because its <dt>/<dd> pairs have no margin
    between them to absorb the difference.
    """
    rect = lay.blockBoundingRect(block)
    layout = block.layout()
    first = layout.lineAt(0).y() if layout and layout.lineCount() else 0.0
    return int((rect.top() + first) // body_h)


def _first_orphan_heading(doc, body_h: float, skip: "set | None" = None):
    """``(heading, following_block)`` for the topmost orphan, or None.

    *skip* holds headings a caller has already pushed, so one that will not
    move does not hide every later orphan in the document.
    """
    lay = settled_layout(doc)
    block = doc.begin()
    while block.isValid():
        nxt = block.next()
        while nxt.isValid() and not nxt.text().strip():
            nxt = nxt.next()
        if (_is_heading(block) and nxt.isValid()
                and (not skip or block.position() not in skip)
                and QTextCursor(block).currentTable() is None):
            if _line_page(lay, nxt, body_h) > _line_page(lay, block, body_h):
                return block, nxt
        block = block.next()
    return None


# ---------------------------------------------------------------------------
# Painting
# ---------------------------------------------------------------------------
def draw_wordmark(painter: QPainter, right_x: float, size_px: int = 22,
                  top: float = 1.0) -> float:
    """Paint the ChromIQ wordmark with its right edge at *right_x*.

    "Chrom" in Instrument Serif near-black, "IQ" bold-italic in the magenta
    accent — the app masthead's own construction. Returns the width it took.
    """
    reg = QFont()
    reg.setPixelSize(size_px)
    reg.setFamilies(["Instrument Serif", "Georgia", "Times New Roman", "serif"])
    ital = QFont(reg)
    ital.setBold(True)
    ital.setItalic(True)
    fm_r, fm_i = QFontMetricsF(reg), QFontMetricsF(ital)
    chrom_w = fm_r.horizontalAdvance("Chrom")
    iq_w = fm_i.horizontalAdvance("IQ")
    x = right_x - (chrom_w + iq_w)
    base = top + fm_r.ascent()
    painter.save()
    painter.setFont(reg)
    painter.setPen(QColor(WORDMARK_INK))
    painter.drawText(QPointF(x, base), "Chrom")
    painter.setFont(ital)
    painter.setPen(QColor(WORDMARK_ACCENT))
    painter.drawText(QPointF(x + chrom_w - 1.0, base), "IQ")
    painter.restore()
    return chrom_w + iq_w


def draw_colour_line(painter: QPainter, width: float, y: float,
                     thickness: float = 3.0) -> None:
    """The five-segment spectrum bar — one segment per tab, in tab order."""
    seg = width / len(TAB_COLORS)
    for i, col in enumerate(TAB_COLORS):
        painter.fillRect(QRectF(i * seg, y, seg, thickness), QColor(col))


def render_paged(doc, device, *, page_w: float, page_h: float,
                 header_h: float = 34.0, footer_h: float = 22.0,
                 draw_header=None, footer_text=None,
                 apply_rules: bool = True, scale: float = 1.0) -> int:
    """Paint *doc* onto *device* page by page, with our own header and footer.

    The document is given a page the size of the BODY, so it paginates itself
    into the space that is really left once the bands are taken off. Returns
    the number of pages painted.

    *draw_header* is called as ``draw_header(painter, page_index, page_w,
    header_h)``; the default paints the wordmark and the colour line.
    *footer_text* is called as ``footer_text(page_index, total)`` and its result
    is drawn CENTRED — Qt's own page number is right-aligned, which is what
    Knut asked to change.

    *page_w* / *page_h* are in the document's own units — 96-dpi pixels, the
    space its ``px`` sizes are written in. *scale* converts those to the
    device's: pass ``device.resolution() / 96`` for a device that prints at
    some other resolution and cannot be talked out of it. A printer is exactly
    that — see :func:`ui.help_card_print.render_card`.
    """
    body_h = page_h - header_h - footer_h
    doc.setPageSize(QSizeF(page_w, body_h))
    if apply_rules:
        repeat_table_headers(doc)
        paginate_tables(doc, body_h)
        avoid_split_rows(doc, body_h)
        avoid_orphan_headings(doc, body_h)

    if draw_header is None:
        def draw_header(painter, _pg, width, band_h):        # noqa: ARG001
            draw_wordmark(painter, width)
            draw_colour_line(painter, width, band_h - 4.0)

    if footer_text is None:
        def footer_text(pg, total):
            return tr("Page {n} of {total}").format(n=pg + 1, total=total)

    painter = QPainter(device)
    try:
        if scale != 1.0:
            painter.scale(scale, scale)
        layout = settled_layout(doc)
        # `pageCount()` IS ONLY EVER RIGHT ABOUT A FINISHED LAYOUT — hence the
        # `settled_layout` above rather than a bare `documentLayout()`. It is
        # derived from the document's height, so it can never be too small for
        # the content it knows about; it can only be perfectly right about a
        # document that has been ruined, which is how a card once printed on
        # four sheets with three sheets' worth of it missing. See
        # :func:`settled_layout`.
        total = max(1, doc.pageCount())
        foot_font = QFont()
        foot_font.setPixelSize(10)
        for pg in range(total):
            if pg > 0:
                device.newPage()
            draw_header(painter, pg, page_w, header_h)
            painter.save()
            # CLIP THE BODY BAND. `PaintContext.clip` tells the layout which
            # slice to draw, but it does not stop an element from painting
            # outside it: the tail of an over-tall image landed on top of the
            # header, over the wordmark. The painter's own clip does.
            painter.setClipRect(QRectF(0.0, header_h, page_w, body_h))
            painter.translate(0.0, header_h - pg * body_h)
            ctx = QAbstractTextDocumentLayout.PaintContext()
            ctx.clip = QRectF(0, pg * body_h, page_w, body_h)
            layout.draw(painter, ctx)
            painter.restore()
            text = footer_text(pg, total)
            if text:
                painter.save()
                painter.setPen(QColor(120, 120, 120))
                painter.setFont(foot_font)
                painter.drawText(
                    QRectF(0, page_h - footer_h + 2, page_w, footer_h - 2),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                    text)
                painter.restore()
    finally:
        painter.end()
    return total
