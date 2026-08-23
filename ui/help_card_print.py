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
from typing import Any

from core.i18n import tr
from core.logger import get_logger
from core.version import APP_VERSION

log = get_logger(__name__)

#: Print styling. Set on the QTextDocument, so it applies to every card kind.
_PRINT_CSS = """
body { font-family: -apple-system, "Segoe UI", "Helvetica Neue", sans-serif;
       color: #000000; font-size: 10.5pt; }
h1   { font-size: 19pt; margin: 0 0 2pt 0; }
p.sub{ font-size: 10pt; color: #444444; margin: 0 0 14pt 0; }
h2, h3 { font-size: 12pt; margin: 14pt 0 4pt 0; }
table{ border-collapse: collapse; width: 100%; }
td, th { border: 1px solid #999999; padding: 3pt 5pt;
         vertical-align: top; font-size: 10pt; }
th   { background: #eeeeee; }
dt   { font-weight: bold; margin-top: 7pt; }
dd   { margin: 0 0 0 14pt; }
ol   { margin-left: 14pt; }
li   { margin-bottom: 5pt; }
p.foot { color: #666666; font-size: 8.5pt; margin-top: 16pt; }
"""

#: The tab a step belongs to, for the printed step list. The dialog shows this
#: as a coloured badge; on paper it is the tab's name in front of the step.
_TAB_NAMES = ("Create Chart", "Measure", "Build Profile", "Check & Refine")


def _tab_name(idx: Any) -> str:
    """The tab's name, translated — a printed card is read in the user's own
    language, and these were the one thing on the page that stayed English."""
    try:
        return tr(_TAB_NAMES[int(idx)])
    except (TypeError, ValueError, IndexError):
        return ""


#: Fallback page size, in millimetres — A4 less a 15 mm margin each side. Used
#: only when nobody has told us the real one (a preview, a test).
_PAGE_WIDTH_MM = 180.0
_PAGE_HEIGHT_MM = 225.0
#: A QTextDocument lays HTML out in 96-dpi pixels, so anything that has to FIT
#: the page is measured in those.
_PX_PER_MM = 96.0 / 25.4
_PAGE_WIDTH_PX = int(_PAGE_WIDTH_MM * _PX_PER_MM)
_PAGE_HEIGHT_PX = int(_PAGE_HEIGHT_MM * _PX_PER_MM)
#: Share of the printable height a single picture may take. See _diagram_html.
_DIAGRAM_HEIGHT_HEADROOM = 0.80


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
        # HEADROOM, MEASURED. A picture the exact height of the printable area
        # is still split across two pages — it is placed in the text flow, so it
        # has to fit what is LEFT of a page, and the paragraph's own spacing eats
        # into that. Printing this card to A4, Letter, A4-landscape, A5, A6 and
        # A4-with-45 mm-margins: at 1.00 and 0.92 of the height every size split
        # it; at 0.85 only A6 still did; at 0.80 none of them do.
        ratio = size.height() / size.width()
        usable_h = height_px * _DIAGRAM_HEIGHT_HEADROOM
        shown_w = max(1, min(width_px, int(usable_h / ratio)))
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
    parts: list[str] = [f"<h1>{title}</h1>"]
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
        from ui.file_guide import file_guide_html
        parts.append(file_guide_html())
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
        parts.append(str(wf.get("body") or ""))
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
            parts.append(f"<li>{lead}{html.escape(str(text))}{tail}</li>")
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
    doc.setTextWidth(width_mm * _PX_PER_MM)
    return doc


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
    return _PAGE_WIDTH_MM, _PAGE_HEIGHT_MM


def print_card(wf: dict, parent=None, lang: str = "en") -> bool:
    """Show the system print dialog for the card *wf*.

    Returns True when the user went ahead. On macOS the print dialog's own PDF
    menu covers "save as PDF", which is what Knut asked for; the same dialog on
    Windows and Linux offers "Print to File (PDF)".
    """
    try:
        from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
    except ImportError as exc:  # pragma: no cover — QtPrintSupport is bundled
        # RAISE, don't return False. The caller reads False as "the user
        # cancelled" and says nothing, so a missing print module would look
        # exactly like a deliberate Cancel — the silent-failure shape this
        # whole path was given a message for.
        log.warning("QtPrintSupport is unavailable; cannot print the help card")
        raise RuntimeError("QtPrintSupport is unavailable") from exc

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setDocName(str(wf.get("title") or "ChromIQ Help"))
    dlg = QPrintDialog(printer, parent)
    dlg.setWindowTitle(tr("Print this help card"))
    if not _exec_print_dialog(dlg):
        return False
    # The size is read AFTER the dialog: that is where the user picks the paper.
    w_mm, h_mm = printable_size_mm(printer)
    build_document(wf, width_mm=w_mm, height_mm=h_mm, lang=lang).print(printer)
    return True


def _exec_print_dialog(dlg) -> bool:
    """One line, on its own, so the test suite can stub it.

    A native print dialog opened during a headless run blocks for ever;
    ``tests/conftest.py`` replaces this the way it already replaces the Print
    tab's own dialog.
    """
    from PyQt6.QtWidgets import QDialog
    return dlg.exec() == QDialog.DialogCode.Accepted
