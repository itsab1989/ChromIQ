"""A colour block must be findable against the page it sits on.

The swatch was written as `border:1px solid <edge>` on an inline span. **Qt's
rich text ignores it.** Rendered on its own against the report ground and
counted, the border colour came back at ZERO pixels; a first probe that included
the text beside the swatch found the colour and was wrong, because antialiased
glyphs produce every shade of grey there is.

So a patch close to the page ground had no edge to find. Photographed on screen
in the dark report palette, a dark navy patch (`#191946`) on the report ground
(`#1f1f1f`) read as an empty cell in a table where every other row showed a
colour. The light palette and every PDF have the same hole at the other end:
paper white, which is one of the eight cube corners printed on the page a user
hands to a customer.

The edge is a second span behind the fill now. This test RENDERS the markup and
counts pixels, because that is the only kind of test the old code would have
failed: every assertion about the HTML string passed while nothing was drawn.
"""
from __future__ import annotations

import pytest

_GROUND = "#1f1f1f"
_NEAR_GROUND_FILL = "#191946"      # the navy that vanished, measured on screen


def _render(markup: str, ground: str = _GROUND):
    """The markup alone on *ground*, as an image. No text anywhere near it."""
    from PyQt6.QtCore import QSizeF
    from PyQt6.QtGui import QColor, QImage, QPainter, QTextDocument
    doc = QTextDocument()
    doc.setHtml(f"<div style='background:{ground}'>{markup}</div>")
    doc.setPageSize(QSizeF(300, 60))
    img = QImage(300, 60, QImage.Format.Format_RGB32)
    img.fill(QColor(ground))
    p = QPainter(img)
    doc.drawContents(p)
    p.end()
    return img


def _count(img, colour: str) -> int:
    from PyQt6.QtGui import QColor
    want = QColor(colour).name()
    return sum(1 for y in range(img.height()) for x in range(img.width())
               if img.pixelColor(x, y).name() == want)


def test_the_fill_is_drawn(qapp):
    from ui.dialogs.measurement_report_dialog import _swatch
    assert _count(_render(_swatch(_NEAR_GROUND_FILL)), _NEAR_GROUND_FILL) > 50


def test_the_edge_is_drawn(qapp):
    """THE WHOLE POINT. A swatch whose fill is the ground colour must still be
    visible, and only the edge can do that."""
    from ui.dialogs.measurement_report_dialog import _C, _swatch
    img = _render(_swatch(_NEAR_GROUND_FILL))
    assert _count(img, _C["swatch_edge"]) > 20, \
        "the edge colour is nowhere in the rendered swatch"


def test_a_swatch_the_colour_of_the_page_is_still_findable(qapp):
    """Paper white on the light palette, composite black on the dark one."""
    from ui.dialogs.measurement_report_dialog import _C, _swatch
    img = _render(_swatch(_GROUND))
    assert _count(img, _C["swatch_edge"]) > 20


def test_the_old_markup_would_have_failed_this(qapp):
    """THE MUTATION, WRITTEN DOWN. `border` on an inline span draws nothing, and
    this is the proof that the test above is not passing on something else."""
    from ui.dialogs.measurement_report_dialog import _C
    edge = _C["swatch_edge"]
    old = (f"<span style='background-color:{_NEAR_GROUND_FILL};"
           f"color:{_NEAR_GROUND_FILL};border:1px solid {edge}'>"
           "&nbsp;&nbsp;&nbsp;</span>")
    assert _count(_render(old), edge) == 0


@pytest.mark.parametrize("ground", ["#ffffff", "#1f1f1f"])
def test_it_holds_on_both_report_palettes(qapp, ground):
    from ui.dialogs import measurement_report_dialog as M
    for name, palette in (("light", M._LIGHT_REPORT), ("dark", M._DARK_REPORT)):
        saved = dict(M._C)
        M._C = dict(palette)
        try:
            img = _render(M._swatch(ground), ground=ground)
            assert _count(img, palette["swatch_edge"]) > 20, (name, ground)
        finally:
            M._C = saved
