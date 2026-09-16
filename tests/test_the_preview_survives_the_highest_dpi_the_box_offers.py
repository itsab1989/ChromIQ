"""A chart the app agreed to build must have a picture, at every dpi.

**AT 1200 dpi ON A4 THE WHOLE PREVIEW PANEL WAS AN ERROR STRING (B8-244).**
`TiffPreview._pil_to_pixmap` encoded the rendered page as a PNG and handed the
bytes to `QPixmap.loadFromData`, which reads through `QImageIOHandler` and
rejects anything over `QImageReader`'s allocation limit. That limit is 256 MB
by default and an A4 page at 1200 dpi is 9921 x 14031, which is 417 MB, so Qt
printed

    qt.gui.imageio: QImageIOHandler: Rejecting image as it exceeds the current
    allocation limit of 256 megabytes

and the panel put this in place of the chart:

    Preview error:
    QPixmap.loadFromData failed for (9921, 14031) RGB image

Driven on screen and photographed
(`~/Desktop/ChromIQ-beta18-proof/beta19-round-2/window/Q8-dpi1200.png`): the
chart was written, "Measured from Preview" reported all four margins, "Chart
layout information" reported 667 patches, and there was no picture and nothing
a reader could act on. The dpi box accepts 72 to 1200 and A4 is the default
paper, so it takes two ordinary controls to reach; 300 and 600 dpi were fine in
the same run.

A `QImage` built over the buffer the renderer already holds is not read through
a handler, so no limit applies, and `QPixmap.fromImage` copies it. It is also
strictly less work than encoding and then decoding a PNG of the same picture on
every preview render.

**The resolution is not reduced, and must not be:** `_refresh_image` hands this
pixmap straight to `_measure_own_margin`, which is where the "Measured from
Preview" numbers come from.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from PIL import Image                                           # noqa: E402

from ui.tiff_preview import TiffPreview                          # noqa: E402


@pytest.fixture(autouse=True)
def _app(qapp):
    return qapp


@pytest.mark.parametrize("size", [
    (2480, 3508),        # A4 at 300 dpi
    (4961, 7016),        # A4 at 600 dpi
    (9921, 14031),       # A4 at 1200 dpi, the state that had no picture
])
def test_every_page_the_dpi_box_can_produce_becomes_a_pixmap(size):
    """MUTATION: go back to `img.save(PNG)` + `QPixmap.loadFromData` and the
    1200 dpi case raises, exactly as it did on screen."""
    img = Image.new("RGB", size, (255, 255, 255))
    px = TiffPreview._pil_to_pixmap(img)
    assert not px.isNull()
    assert (px.width(), px.height()) == size, (
        "the preview was scaled to fit the limit, and “Measured from Preview” "
        "is taken off this pixmap")


def test_the_pixels_are_the_renderer_s_own():
    """A wrong stride or channel order would show as a scrambled preview and
    would move every measured margin with it."""
    from PyQt6.QtGui import qBlue, qGreen, qRed
    img = Image.new("RGB", (7, 5), (255, 255, 255))
    img.putpixel((0, 0), (255, 0, 0))
    img.putpixel((6, 4), (0, 0, 255))
    img.putpixel((3, 2), (0, 128, 64))
    out = TiffPreview._pil_to_pixmap(img).toImage()
    for xy, want in (((0, 0), (255, 0, 0)), ((6, 4), (0, 0, 255)),
                     ((3, 2), (0, 128, 64))):
        rgb = out.pixel(*xy)
        assert (qRed(rgb), qGreen(rgb), qBlue(rgb)) == want, (
            f"{xy}: the preview's pixels are not the page's")


def test_a_paletted_or_grey_page_still_converts():
    """`_load_frame` can hand over a mode this path does not take directly."""
    for mode in ("L", "P", "RGBA"):
        px = TiffPreview._pil_to_pixmap(Image.new(mode, (9, 9)))
        assert not px.isNull(), mode


def test_the_png_round_trip_is_gone():
    """It was the whole mechanism, and it cost a PNG encode plus decode of the
    full page on every render as well.

    MUTATION: put `loadFromData` back and this goes red.
    """
    import ast
    import inspect
    import textwrap
    fn = ast.parse(textwrap.dedent(
        inspect.getsource(TiffPreview._pil_to_pixmap))).body[0]
    if (fn.body and isinstance(fn.body[0], ast.Expr)
            and isinstance(fn.body[0].value, ast.Constant)):
        fn.body = fn.body[1:]          # the docstring names it on purpose
    src = ast.unparse(fn)
    assert "loadFromData" not in src, (
        "the preview decodes a PNG again, so it is back under "
        "QImageReader's allocation limit")
    assert "QPixmap.fromImage" in src
