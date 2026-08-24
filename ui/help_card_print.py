"""Print a Help card — and, through the print dialog, save it as a PDF (#164).

Knut, 2026-08-23: *"That it would be possible to print a currently viewed help
card via normal print dialog (which also would allow saving as pdf). This would
make it easier for a user to have something in their hand while working, for
example printing the keyboard shortcuts."*

**The card on screen is four different things**, and only one of them is already
HTML, so "just print the widget" would have quietly dropped the rest:

===================  =====================================================
card ``kind``        where its content lives
===================  =====================================================
``files`` /          one HTML string from ``file_guide_html()`` /
``richtext`` /       ``keyboard_shortcuts_html()`` / ``main_actions_html()``
``shortcuts`` /      / the card's own ``body``
``main_actions``
``glossary``         the ``GLOSSARY`` list, built on screen as widget rows
``getting_started``  a LIST of HTML blocks, plus a diagram painted by a
                     custom widget — which is in no HTML at all
default              ``steps`` tuples, rendered as badge + label rows
===================  =====================================================

:func:`card_html` gives every one of them a printable form, the diagram
included: it is painted into an image and embedded in the document, because a
workflow card without its workflow picture is not the card the user was reading.

The page is deliberately plain — black on white, no theme colours. It is going
on paper, and the dark theme's own palette would print as a solid black sheet.
"""
from __future__ import annotations

import html
import re
from typing import Any

from PyQt6.QtCore import QSizeF

from core.i18n import tr
from core.logger import get_logger
from ui.pdf_layout import (draw_colour_line, draw_wordmark,
                           render_paged)
from core.version import APP_VERSION

log = get_logger(__name__)

#: Print styling. Set on the QTextDocument, so it applies to every card kind.
_PRINT_CSS = """
/* EVERYTHING IN px — SIZES AND SPACING ALIKE.

   Spacing first: Qt IGNORES a margin in points. `margin-top: 14pt` is silently
   zero, as are cm and pt paddings (measured). Every space in this sheet was
   once doing nothing — no blank line above a heading, no gap between list
   items, no indent on a definition — which was most of what Knut reported as
   bullets printing "as one continuous block of messy text".

   SIZES ARE px FOR A DIFFERENT AND WORSE REASON. A font size in `pt` IS
   honoured, but Qt resolves it against the PRIMARY SCREEN's logical DPI — and
   that is 72 on macOS against 96 under `QT_QPA_PLATFORM=offscreen`. So the
   same card printed 25 % smaller on Knut's Mac than in every test we ran:
   10.5pt body text was 14 px on CI and 11 px on his sheet, while the folder
   guide's <pre> stayed at its absolute 12 px and towered over it (#164, his
   report A2). 37 pages against CI's 42, for the same 18 cards. Pixels are
   absolute, so the printed page is now the same on macOS, Windows, Linux and
   CI, and what the tests measure is what he gets.

   The document is laid out at 96 dpi, so 1 px is 1/96 inch on paper whatever
   the printer's resolution. The values below are the px each old pt size
   resolved to under the 96-dpi tests, so the printed card is unchanged there
   and it is macOS that stops shrinking.

   DO NOT WRITE A SIZE IN pt HERE AGAIN — tests/test_help_card_printing.py
   fails on it. Two related traps, both measured: a `font-size` in pt inside an
   inline style= attribute is ignored outright, and <h1> ignores its font size
   from any source at all, which is why card titles are a styled <p>. */
body { font-family: -apple-system, "Segoe UI", "Helvetica Neue", sans-serif;
       color: #000000; font-size: 14px; }
p.title { font-size: 22px; font-weight: bold; margin: 0 0 3px 0; }
p.sub{ font-size: 13px; color: #444444; margin: 0 0 18px 0; }
h2, h3 { font-size: 16px; margin: 18px 0 6px 0; }
table{ border-collapse: collapse; width: 100%; }
td, th { border: 1px solid #999999; vertical-align: top; font-size: 13px; }
th   { background: #eeeeee; }
dt   { font-weight: bold; margin: 14px 0 2px 0; }
dd   { margin: 0 0 4px 18px; }
ol, ul { margin-left: 18px; }
li   { margin-bottom: 10px; }
/* A prose card converted to a real list (CMYK+N) needs tighter items than a
   steps card: at 10 px it spilled one line onto a second sheet, which is the
   waste Knut objected to in the first place. Scoped to that list so the steps
   cards keep the 10 px they were given in #164. */
ol.tight li { margin-bottom: 4px; }
p.foot { color: #666666; font-size: 11px; margin-top: 20px; }
"""
#: The tab a step belongs to, for the printed step list. The dialog shows this
#: as a coloured badge; on paper it is the tab's name in front of the step.
#:
#: KEYED BY THE NUMBER THE STEP CARRIES, WHICH IS THE NUMBER ON THE TAB.
#: The step tuples hold 1-5, matching the tab strip's own "1. Create Chart" …
#: "5. Check & Refine" (ui/main_window.py). The first version of this table was
#: a 0-based tuple of four names with Print Chart missing, so every printed step
#: named a different tab from the one it means — "Print an existing test chart"
#: told the reader to go to Measure to print (#164, Basti).
_TAB_NAMES = {
    1: "Create Chart",
    2: "Print Chart",
    3: "Measure",
    4: "Build Profile",
    5: "Check & Refine",
}


def _tab_name(idx: Any) -> str:
    """The tab's name, translated — a printed card is read in the user's own
    language, and these were the one thing on the page that stayed English."""
    try:
        name = _TAB_NAMES.get(int(idx))
    except (TypeError, ValueError):
        return ""
    return tr(name) if name else ""


#: Fallback page size, in millimetres — A4 less a 15 mm margin each side. Used
#: only when nobody has told us the real one (a preview, a test).
_PAGE_WIDTH_MM = 180.0
_PAGE_HEIGHT_MM = 225.0

#: The PAGE to fall back on when a device will not say how big its own is —
#: A4 less the 15 mm margins ChromIQ asks for. Not to be confused with
#: `_PAGE_HEIGHT_MM` above, which bounds the BODY (the page less our header and
#: footer bands) and is 42 mm shorter. `printable_size_mm` returned that one by
#: mistake, which left 60 mm blank at the foot of every sheet and floated the
#: page number above the paper edge (#164 review).
_FALLBACK_PAGE_MM = (180.0, 267.0)
#: A QTextDocument lays HTML out in 96-dpi pixels, so anything that has to FIT
#: the page is measured in those.
_PX_PER_MM = 96.0 / 25.4
_PAGE_WIDTH_PX = int(_PAGE_WIDTH_MM * _PX_PER_MM)
_PAGE_HEIGHT_PX = int(_PAGE_HEIGHT_MM * _PX_PER_MM)
#: Height of the printed header band (wordmark + spectrum bar) and of the
#: footer band (the centred page number), in 96-dpi pixels: 34 px is 9 mm.
_HEADER_H = 34.0
_FOOTER_H = 22.0
#: Room left for a figure's own paragraph spacing, in 96-dpi pixels.
_FIGURE_ALLOWANCE_PX = 28.0
#: Width of one character of the folder diagram on paper, in mm. The <pre> is
#: 12 px (ui/file_guide.py) and a 96-dpi pixel is 25.4/96 mm, so a character of
#: Menlo — whose advance is 0.6 em — is 12 x 0.6 x 25.4/96 = 1.905 mm. Only used
#: to keep the diagram inside a NARROW page; on A4 it never binds.
_TREE_CHAR_MM = 1.905


def _diagram_html(doc, width_px: int = _PAGE_WIDTH_PX, lang: str = "en",
                  height_px: int = _PAGE_HEIGHT_PX) -> str:
    """The Getting-Started workflow diagram, embedded in *doc* as a resource.

    Returns the ``<img>`` that refers to it, or "" when the drawing is not
    available — a missing picture must never cost the user the rest of the card.

    One SVG per language, English as the fallback, exactly as the on-screen card
    chooses it (``WelcomeDialog._gs_workflow_diagram_label``). It is rendered on
    WHITE here rather than in the theme's colours: this one is going on paper.
    """
    try:
        from pathlib import Path

        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QImage, QPainter, QTextDocument
        from PyQt6.QtSvg import QSvgRenderer

        from core.resource_path import resource_path

        svg = resource_path(f"assets/help/workflow/{lang}.svg")
        if not Path(svg).is_file():
            svg = resource_path("assets/help/workflow/en.svg")
        if not Path(svg).is_file():
            return ""
        ren = QSvgRenderer(str(svg))
        if not ren.isValid():
            return ""
        size = ren.defaultSize()
        if not size.isValid() or size.width() <= 0:
            return ""
        # FIT THE PAGE IN BOTH DIRECTIONS, THEN RENDER BIG.
        #
        # A QTextDocument lays HTML out at 96 dpi, and it neither shrinks an
        # image that is too wide (it CLIPS it at the page edge) nor one that is
        # too tall (it repeats it on the next page). At a fixed 900 px the
        # workflow diagram lost its whole right-hand column and printed twice.
        # So the placement is solved against the page, and only the BITMAP is
        # oversampled — 3x — so it still prints crisply.
        # PORTRAIT fits both directions, so the whole drawing lands on one
        # page. LANDSCAPE fits the width only and is allowed to run on, which is
        # Knut's own ruling: *"it should be ok to let the drawing image overflow
        # to the next page, as the image is tall and would become too small if
        # whole image height would be adapted to landscape page height."*
        ratio = size.height() / size.width()
        portrait = height_px >= width_px
        # A little off the height: the picture sits in a paragraph of its own,
        # and that paragraph's spacing counts against the page as much as the
        # picture does. Sized to the FULL body height it overflows by those few
        # pixels and is split after all — measured, with its tail landing on the
        # next page over the header.
        usable_h = height_px - _FIGURE_ALLOWANCE_PX
        shown_w = max(1, min(width_px, int(usable_h / ratio)) if portrait
                      else width_px)
        shown_h = max(1, round(shown_w * ratio))
        draw_px = shown_w * 3
        img = QImage(draw_px, max(1, round(draw_px * ratio)),
                     QImage.Format.Format_ARGB32)
        img.fill(0xFFFFFFFF)
        p = QPainter(img)
        ren.render(p)
        p.end()
        url = QUrl("chromiq://help/diagram.png")
        doc.addResource(QTextDocument.ResourceType.ImageResource, url, img)
        # …AND A PAGE BREAK IN FRONT OF IT. Headroom alone is not enough: a
        # picture placed low on a page is still split, whatever its height. The
        # two together are what produce a single, whole diagram — measured on
        # A4, Letter, A4-landscape, A5, A6 and A4-with-45 mm margins, all of
        # which split it with either one on its own.
        return (f'<p style="page-break-before: always"><img '
                f'src="{url.toString()}" '
                f'width="{shown_w}" height="{shown_h}"></p>')
    except Exception:      # noqa: BLE001 — the rest of the card still prints
        log.debug("could not embed the workflow diagram", exc_info=True)
        return ""


#: A tag opener is enough to tell markup from prose — the same question Qt's own
#: `mightBeRichText` answers, which PyQt6 does not expose. Anchored on a real tag
#: name followed by a delimiter, so prose like "a < b and c > d" is not mistaken
#: for markup.
_TAG_RE = re.compile(r"<(p|div|table|tr|td|th|ul|ol|li|br|b|i|h[1-6]|span|pre)"
                     r"(\s|>|/>)", re.I)


def _as_html(text: str) -> str:
    """Prose → HTML that keeps the shape the author gave it.

    A card body that is plain text (the CMYK+N card is written that way, and
    every step's text can be) was being pasted straight into the page, where
    HTML throws newlines away: numbered items and bullets ran together into one
    grey block, and the blank lines between them vanished (#164, Knut). Blank
    lines become paragraph breaks and single newlines become line breaks, so
    print matches what the card shows on screen.

    Markup is passed through untouched — there the newlines really are just
    formatting whitespace.
    """
    if _TAG_RE.search(text):
        return text
    paras = [p for p in re.split(r"\n\s*\n", text)]
    out = []
    for para in paras:
        if not para.strip():
            continue
        out.append("<p>" + "<br>".join(html.escape(ln) for ln in
                                       para.split("\n")) + "</p>")
    return "".join(out)


def card_html(wf: dict, doc=None, lang: str = "en",
              width_mm: float = _PAGE_WIDTH_MM,
              height_mm: float = _PAGE_HEIGHT_MM) -> str:
    """The card *wf* as one self-contained HTML document, ready to print.

    *doc* is the :class:`QTextDocument` the HTML will be set on; it is needed
    only so an embedded image can be registered as a resource on it.
    """
    kind = wf.get("kind")
    title = html.escape(str(wf.get("title") or ""))
    subtitle = html.escape(str(wf.get("subtitle") or ""))
    # A STYLED <p>, NOT AN <h1>. Qt fixes an <h1>'s size from its own default
    # and ignores every font-size it is given — sheet rule, inline style, pt,
    # px, em, %: all measured, all identical. So the 19pt in _PRINT_CSS was
    # dead, the title rendered at 26 px on macOS, and "Calibrate my printer
    # (and how that differs from a profile)" wrapped to two lines and pushed
    # the tail of the card onto a second page (#164, Knut A3).
    parts: list[str] = [f'<p class="title">{title}</p>']
    if subtitle:
        parts.append(f'<p class="sub">{subtitle}</p>')

    if kind == "glossary":
        from ui.dialogs.welcome_dialog import GLOSSARY
        parts.append("<dl>")
        for term, definition in sorted(GLOSSARY, key=lambda e: e[0].lower()):
            parts.append(f"<dt>{html.escape(term)}</dt>"
                         f"<dd>{html.escape(definition)}</dd>")
        parts.append("</dl>")
    elif kind == "files":
        from ui.file_guide import file_guide_html, tree_lines, tree_text_column
        # The folder diagram is a <pre>: it cannot reflow, so on a page narrower
        # than the Help card it would simply be cut off at the edge. Ask the
        # guide for a text column that fits. On A4 and anything wider this comes
        # out at the card's own 62 characters and nothing changes.
        chars = max(24, min(62, int(width_mm / _TREE_CHAR_MM)
                            - tree_text_column()))
        parts.append(file_guide_html(chars))
    elif kind == "shortcuts":
        from ui.keyboard_help import keyboard_shortcuts_html
        parts.append(keyboard_shortcuts_html())
    elif kind == "main_actions":
        from ui.main_actions import main_actions_html
        parts.append(main_actions_html())
    elif kind == "getting_started":
        from ui.getting_started import getting_started_sections
        for key, block in getting_started_sections():
            parts.append(block)
            if key == "workflow" and doc is not None:
                parts.append(_diagram_html(
                    doc, width_px=max(1, int(width_mm * _PX_PER_MM)), lang=lang,
                    height_px=max(1, int(height_mm * _PX_PER_MM))))
    elif kind == "richtext":
        # Same converter the on-screen card uses, so the two cannot drift.
        from ui.dialogs.welcome_dialog import numbered_prose_html
        raw = str(wf.get("body") or "")
        parts.append(numbered_prose_html(raw) or _as_html(raw))
    else:
        # Numbered steps. The badge is a tab number on screen; on paper the tab
        # is named, because a printed sheet has no coloured tabs to point at.
        parts.append("<ol>")
        for step in wf.get("steps") or ():
            tab, text = step[0], step[1]
            optional = bool(step[2]) if len(step) > 2 else False
            name = _tab_name(tab)
            lead = f"<b>{html.escape(name)}</b> — " if name else ""
            tail = f" <i>({tr('optional')})</i>" if optional else ""
            # …and the step's own text may carry its own paragraphs and lists.
            body_html = _as_html(str(text))
            body_html = re.sub(r"^<p>|</p>$", "", body_html)   # first para inline
            parts.append(f"<li>{lead}{body_html}{tail}</li>")
        parts.append("</ol>")

    parts.append('<p class="foot">'
                 + html.escape(tr("ChromIQ {version} — {title}").format(
                     version=APP_VERSION, title=wf.get("title") or ""))
                 + "</p>")
    return "<body>" + "".join(parts) + "</body>"


def build_document(wf: dict, width_mm: float = _PAGE_WIDTH_MM, lang: str = "en",
                   height_mm: float = _PAGE_HEIGHT_MM):
    """A :class:`QTextDocument` of *wf*, laid out for a page *width_mm* across.

    *height_mm* bounds anything that has to land on ONE page — today just the
    Getting-Started diagram. Both default to A4-less-margins and are overridden
    by :func:`print_card` with the printer's real printable area, because the
    page is not always A4: at the old fixed numbers an A5 print lost a third of
    the diagram off the right edge and repeated it on the next page, which is
    the very fault this was written to fix.
    """
    from PyQt6.QtGui import QTextDocument

    doc = QTextDocument()
    doc.setDefaultStyleSheet(_PRINT_CSS)
    doc.setHtml(card_html(wf, doc, lang=lang, width_mm=width_mm,
                          height_mm=height_mm))
    # setPageSize, NOT setTextWidth.
    #
    # A document with only a text width is UNPAGINATED, and `QTextDocument.print`
    # then takes a different path: it clones the document, lays it out again at
    # the PRINTER's resolution, and adds a 2 cm margin of its own to the root
    # frame. Two faults follow, and they are the ones Knut and Basti reported.
    # Every card printed into a 140 mm column inside the 180 mm page we had
    # asked for. And `px` font sizes — which the cards are written in — were
    # resolved against the printer's dots instead of the screen's, so the folder
    # guide's headings and its whole directory tree came out as an unreadable
    # smudge, by a factor that changes with the printer's resolution (worse on
    # this 720 dpi Mac than on a 300 dpi Windows driver, which is why it looked
    # like a different bug to different people).
    #
    # Giving the document a PAGE makes it paginate itself, at 96 dpi, in the
    # space we actually have — and `print` then just paints the pages.
    doc.setPageSize(QSizeF(width_mm * _PX_PER_MM, height_mm * _PX_PER_MM))
    return doc


#: Characters a file name cannot carry on the platforms ChromIQ runs on. The
#: print job's name becomes the suggested file name in "Save as PDF", and one of
#: these in it is enough for the system to give up and offer "Untitled.pdf" —
#: which is what the folder guide, "Where are my files?", did (#164, Knut).
_NAME_ILLEGAL = '/\\:*?"<>|'


def document_name(wf: dict) -> str:
    """The print job's name — and so the file name "Save as PDF" suggests.

    Knut: *"the default name of the pdf is 'Untitled.pdf'. It should by default
    have the name of the help card being printed … (remember to remove any
    starting or trailing spaces in the file name)."*
    """
    name = " ".join(str(wf.get("title") or "").split())      # collapse + trim
    name = "".join(c for c in name if c not in _NAME_ILLEGAL).strip(" .")
    return name or "ChromIQ Help"


def printable_size_mm(printer) -> "tuple[float, float]":
    """The printer's paintable area in millimetres, or the A4 fallback.

    Read off the page LAYOUT rather than the paper, so the margins the user's
    driver reserves are already taken off.
    """
    try:
        from PyQt6.QtGui import QPageLayout
        rect = printer.pageLayout().paintRect(QPageLayout.Unit.Millimeter)
        w, h = float(rect.width()), float(rect.height())
        if w > 10.0 and h > 10.0:
            return w, h
    except Exception:      # noqa: BLE001 — fall back rather than fail to print
        log.debug("could not read the printer page layout", exc_info=True)
    return _FALLBACK_PAGE_MM


def save_card_pdf(wf: dict, parent=None, lang: str = "en") -> "Path | None":
    """Write the card straight to a PDF the user names. Returns the path.

    THE SYSTEM'S OWN "Save as PDF" WOULD NOT TAKE OUR NAME. `setDocName` is set,
    and macOS still offered "Untitled.pdf" (#164, Knut). Rather than keep
    guessing at another program's dialog, ChromIQ asks for the file name itself
    — with the card's title already filled in — and writes the PDF with the same
    painter the printer uses, so the page is identical either way.
    """
    from pathlib import Path

    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize, QPdfWriter

    from ui.widgets import save_file_dialog

    # The third argument is Qt's file FILTER, not a label — passing "File name"
    # made the dialog filter on the globs "File" and "name", so it listed no
    # existing PDF at all (#164 review).
    chosen = save_file_dialog(
        parent, tr("Save this help card as a PDF"), tr("PDF documents (*.pdf)"),
        start_path=str(Path.home() / f"{document_name(wf)}.pdf"))
    if not chosen:
        return None
    path = Path(chosen)
    if path.suffix.lower() != ".pdf":
        path = path.with_suffix(".pdf")
    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    writer.setTitle(document_name(wf))
    render_card(wf, writer, lang=lang)
    return path


def print_card(wf: dict, parent=None, lang: str = "en") -> bool:
    """Show the system print dialog for the card *wf*.

    Returns True when the user went ahead, False when they cancelled. Help
    itself treats the two the same — it comes back to the front either way —
    but a caller that could not tell them apart would read a BROKEN print as a
    deliberate Cancel, which is why the ImportError below raises.

    THE SYSTEM DIALOG, NOT ONE OF OURS. Qt can put its own preview window in
    front of it, and beta.2 did; it was thrown out because a second window is
    not what anyone asked for. The system panel on macOS cannot show its own
    preview pane through Qt at all — Apple draws that pane from an
    `NSPrintOperation` asking a real `NSView` for its pages, and Qt presents a
    bare `NSPrintPanel` instead (`qprintdialog_mac.mm`). The Windows common
    print dialog has no preview either, and Qt hides the one in its own Linux
    dialog. So the honest routes to seeing the pages first are the panel's own
    PDF ▸ Open in Preview on macOS, and "Save as PDF…" beside this button
    everywhere.
    """
    try:
        from PyQt6.QtCore import QMarginsF
        from PyQt6.QtGui import QPageLayout, QPageSize
        from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
    except ImportError as exc:  # pragma: no cover — QtPrintSupport is bundled
        # RAISE, don't return False. The caller reads False as "the user
        # cancelled" and says nothing, so a missing print module would look
        # exactly like a deliberate Cancel — the silent-failure shape this
        # whole path was given a message for.
        log.warning("QtPrintSupport is unavailable; cannot print the help card")
        raise RuntimeError("QtPrintSupport is unavailable") from exc

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setDocName(document_name(wf))
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    dlg = QPrintDialog(printer, parent)
    dlg.setWindowTitle(tr("Print this help card"))
    if not _exec_print_dialog(dlg):
        return False
    render_card(wf, printer, lang=lang)
    return True


def render_card(wf: dict, device, *, lang: str = "en") -> int:
    """Paint the card onto a QPrinter or QPdfWriter. Returns the page count.

    The document is laid out in 96-dpi pixels — that is the space its `px`
    sizes and image widths are written in. The DEVICE is not asked to work in
    those units, because a real printer will not:

        ASK A PRINTER FOR 96 dpi AND IT GIVES YOU THE NEAREST IT HAS.
        `QMacPrintEngine::setProperty` snaps the request to the queue's own
        `supportedResolutions()` — 96 became 300 on both printers here — while
        `width()` goes on reporting device pixels at that resolution. Dividing
        those by 96 read a 180 mm page as 562 mm, and the card printed at 32 %
        of its size, crushed into the top third of the sheet. A `QPdfWriter`
        accepts any resolution, so every proof we had was blind to it (#164).

    So: measure the page in millimetres, lay the document out in 96-dpi pixels,
    and scale the painter to whatever the device actually runs at. Text stays
    vector-crisp — and now prints at the printer's full resolution rather than
    at 96 dpi.
    """
    w_mm, h_mm = printable_size_mm(device)
    page_w, page_h = w_mm * 96.0 / 25.4, h_mm * 96.0 / 25.4
    header_h, footer_h = _HEADER_H, _FOOTER_H
    doc = build_document(
        wf, width_mm=w_mm,
        height_mm=(page_h - header_h - footer_h) * 25.4 / 96.0, lang=lang)
    res = float(device.resolution() or 0.0)
    if res <= 0.0:
        # Never seen from a real device, and the alternative is worse than a
        # warning: an unscaled painter against a page measured in millimetres
        # prints the card at some fraction of its size, silently.
        log.warning("the print device reports no resolution; assuming 96 dpi")
        res = 96.0
    return render_paged(doc, device, page_w=page_w, page_h=page_h,
                        header_h=header_h, footer_h=footer_h,
                        draw_header=_draw_card_header(wf),
                        scale=res / 96.0)


def _draw_card_header(wf: dict):
    """The printed header: the ChromIQ wordmark and the five-segment spectrum
    bar (Basti, #164), with the card's own name beside it from page two on so a
    loose sheet still says what it belongs to."""
    def header(painter, pg, width, band_h):
        used = draw_wordmark(painter, width)
        if pg:
            from PyQt6.QtCore import QPointF, Qt
            from PyQt6.QtGui import QColor, QFont
            f = QFont()
            f.setPixelSize(9)
            painter.save()
            painter.setFont(f)
            painter.setPen(QColor(110, 110, 110))
            fm = painter.fontMetrics()
            painter.drawText(QPointF(0.0, 8.0 + fm.ascent()),
                             fm.elidedText(str(wf.get("title") or ""),
                                           Qt.TextElideMode.ElideRight,
                                           int(width - used - 14.0)))
            painter.restore()
        draw_colour_line(painter, width, band_h - 4.0)
    return header


def _exec_print_dialog(dlg) -> bool:
    """One line, on its own, so the test suite can stub it.

    A native print dialog opened during a headless run blocks for ever;
    ``tests/conftest.py`` replaces this the way it already replaces the Print
    tab's own dialog.
    """
    from PyQt6.QtWidgets import QDialog
    return dlg.exec() == QDialog.DialogCode.Accepted
