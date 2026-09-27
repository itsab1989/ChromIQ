"""The note under both preset lists, with its link to "Settings for built-in
presets" (Knut, #182 5851645723, K61, B8-1411).

Knut: *"could you add after the message shown ", or click here <gear-icon>",
where the <gear-icon> is the icon same as what was used in the button for the
used "settings for built-in presets", and which upon clicked opens the same
"settings for built-in presets" window?"*

The note is painted by two widgets ("Select preset"'s pinned footer,
``ui.tabs.tab_chart._PresetListNote``, and the Built-in presets list,
``ui.builtin_preset_popup.BuiltinPresetPopup``), so the one thing they share
is here: a :class:`QTextDocument` of the note, wrapped to a width, in which
the last occurrence of the link words and the gear after them are one anchor.
Both measure its height from the same document and hit-test the anchor with
the same layout, so the part that opens the window is exactly the part drawn
as the link.
"""
from __future__ import annotations

import html

from PyQt6.QtCore import QPointF, QSize, QUrl
from PyQt6.QtGui import QFont, QGuiApplication, QTextDocument

#: The anchor's target. Not a URL anything opens: the widgets compare it.
LINK_HREF = "chromiq:settings-for-built-in-presets"
_GEAR_URL = "chromiq-note:gear"


def gear_image(px: int):
    """The gear of Create Chart's "Settings for built-in presets" button, in
    the colour that button paints it (``set_folder_twin_icon(..., "gear",
    "folder_create")``: magenta in Light and Dark, ACTION in Neutral), at
    ``px`` logical pixels."""
    from ui.widgets import load_folder_twin_icon
    dpr = 1.0
    try:
        screen = QGuiApplication.primaryScreen()
        dpr = float(screen.devicePixelRatio()) if screen is not None else 1.0
    except Exception:      # noqa: BLE001 — a picture, never a blocker
        dpr = 1.0
    icon = load_folder_twin_icon("gear", "folder_create")
    img = icon.pixmap(QSize(px, px), dpr).toImage()
    img.setDevicePixelRatio(dpr)
    return img


def note_document(text: str, link: str, font: QFont, colour: str,
                  width: float) -> QTextDocument:
    """The note as a document ``width`` wide: ``text`` in ``colour``, with
    its last ``link`` words and a gear after them made one anchor
    (:data:`LINK_HREF`). Without ``link`` in ``text``, the plain note."""
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    doc.setDefaultFont(font)
    i = text.rfind(link) if link else -1
    if i < 0:
        body = html.escape(text)
    else:
        px = max(10, round(font.pixelSize() if font.pixelSize() > 0
                           else font.pointSizeF() * 96 / 72))
        doc.addResource(QTextDocument.ResourceType.ImageResource,
                        QUrl(_GEAR_URL), gear_image(px))
        # THREE ANCHORS, ONE LINK (B8-1463). The words and the gear are
        # underlined; the space between them is not, but it is still the
        # link, so a click there opens the window as before. One anchor
        # round all three underlined the space too.
        a = f'<a href="{LINK_HREF}" style="color:{colour}; text-decoration: '
        body = (html.escape(text[:i])
                + a + 'underline;">' + html.escape(link) + '</a>'
                + a + 'none;">&nbsp;</a>'
                + a + f'underline;"><img src="{_GEAR_URL}" width="{px}"'
                  f' height="{px}" style="vertical-align: middle"></a>'
                + html.escape(text[i + len(link):]))
    doc.setHtml(f'<div style="color:{colour}">{body}</div>')
    doc.setTextWidth(max(1.0, float(width)))
    return doc


def link_at(doc: QTextDocument, pos: QPointF) -> bool:
    """Whether ``pos`` (in the document's own coordinates) is on the link."""
    try:
        return doc.documentLayout().anchorAt(pos) == LINK_HREF
    except Exception:      # noqa: BLE001 — a click, never a crash in a slot
        return False
