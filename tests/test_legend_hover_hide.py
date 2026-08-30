"""The legend chip gets out of the way when you point at it.

Basti: *"the legend that shows which part of the patch is measured vs expected
sometimes is over the patches. can we make it so it disappears when the mouse
hovers over it so the user can see what is underneath?"*

The chip is meant to sit in the bottom paper margin, and `tiff_preview.py`'s own
comment concedes that on a chart whose patches reach the edge it lands on the
last row instead — "the lesser evil", against a chip clipped off the page. So
overlapping is a known state, and getting out of the way is the remedy.

THE TRAP THESE PIN. The instant the chip is hidden the pointer is over the
PATCHES, not the chip. A hit test against a rectangle computed only when the
chip is drawn would then say "not hovering", bring it straight back, and
flicker. The rectangle is therefore computed on EVERY paint and remembered.

Real `TiffPreview`, real paint, a real image loaded through `load_tiff`.
"""
import pytest
from PIL import Image
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QColor

CHIP = QColor(20, 20, 20)          # the chip's background, alpha 190 over paper


@pytest.fixture
def preview(qtbot, tmp_path):
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    qtbot.addWidget(p)
    p.resize(700, 700)
    tif = tmp_path / "sheet.tif"
    Image.new("RGB", (600, 600), (245, 245, 245)).save(tif)
    p.load_tiff([tif])
    items = [(QRect(60 + 90 * c, 60 + 90 * r, 80, 80),
              QColor("#3050ff"), QColor("#20c060"), False)
             for r in range(6) for c in range(6)]
    p.set_patch_overlay(0, items, replace_page=True)
    p.show()
    qtbot.waitExposed(p)
    from PyQt6.QtWidgets import QApplication
    QApplication.processEvents()
    return p


def _chip_pixels(p) -> int:
    """Dark pixels INSIDE the chip's own rectangle.

    Scanning the whole widget counts its dark surround too — 2,000 pixels of it
    here, enough to hide the chip's disappearance behind background noise. The
    rectangle is mapped from the image label to the widget, which is the same
    translation the hit test does.
    """
    from PyQt6.QtWidgets import QApplication
    QApplication.processEvents()
    r = p._legend_rect
    if r is None:
        return 0
    label = getattr(p, "_img_label", None)
    off = label.mapTo(p, QPoint(0, 0)) if label is not None else QPoint(0, 0)
    box = r.translated(off).adjusted(-2, -2, 2, 2)
    im = p.grab().toImage()
    n = 0
    for y in range(max(0, box.top()), min(im.height(), box.bottom() + 1)):
        for x in range(max(0, box.left()), min(im.width(), box.right() + 1)):
            c = im.pixelColor(x, y)
            if abs(c.red() - 60) < 34 and abs(c.green() - 60) < 34 \
                    and abs(c.blue() - 60) < 34:
                n += 1
    return n


def _split_pixels(p) -> int:
    """The measured half of the patches. The vacuity guard: if this is zero the
    canvas is empty and 'the chip is gone' means nothing."""
    from PyQt6.QtWidgets import QApplication
    QApplication.processEvents()
    im = p.grab().toImage()
    return sum(1 for y in range(im.height()) for x in range(im.width())
               if im.pixelColor(x, y).green() > 140
               and im.pixelColor(x, y).red() < 120)


def test_the_chip_is_drawn_at_all(preview):
    assert _chip_pixels(preview) > 200, "no chip on screen; the rest proves nothing"


def test_pointing_at_it_takes_it_away_and_leaves_the_patches(preview):
    assert preview._legend_rect is not None, "the chip's rectangle was not recorded"
    before = _chip_pixels(preview)
    preview._legend_pointer = preview._legend_rect.center()
    preview._legend_hidden = preview._legend_is_hidden()
    preview._repaint_label()
    after = _chip_pixels(preview)
    assert after < before / 4, f"the chip is still there ({after} vs {before})"
    # …and the canvas is NOT simply blank, which would pass the line above.
    assert _split_pixels(preview) > 500, "nothing was drawn; vacuous"


def test_it_comes_back_when_the_pointer_leaves(preview):
    before = _chip_pixels(preview)
    preview._legend_pointer = preview._legend_rect.center()
    preview._legend_hidden = True
    preview._repaint_label()
    preview._forget_legend_pointer()
    assert _chip_pixels(preview) == pytest.approx(before, rel=0.15)


def test_the_rectangle_is_refreshed_even_on_the_paint_that_hides_it(preview):
    """The anti-flicker property, stated so that only the real implementation
    passes.

    A first version of this test merely asserted the rectangle was still there
    after a hidden paint — which a broken implementation also satisfies, because
    it leaves the STALE rectangle behind rather than clearing it. Proven by
    mutation: storing the rect only when the chip is visible passed that test.

    What actually distinguishes them is a chip whose placement CHANGES while it
    is hidden. The three wordings differ in width by 70 %, so switching the view
    mode moves and resizes the chip. If the rectangle is only recorded on
    visible paints, the pointer is now being tested against a rectangle that no
    longer describes anything on screen.
    """
    from PyQt6.QtWidgets import QApplication
    preview._legend_pointer = preview._legend_rect.center()
    preview._legend_hidden = True
    preview._repaint_label()
    QApplication.processEvents()
    narrow = QRect(preview._legend_rect)

    preview.set_overlay_mode("measured")      # a much wider wording
    QApplication.processEvents()
    assert preview._legend_rect is not None
    assert preview._legend_rect.width() > narrow.width(), (
        "the chip was re-placed while hidden, but the remembered rectangle "
        "still describes the old one — the pointer is being tested against a "
        "chip that is not there")


def test_pointing_somewhere_else_leaves_it_alone(preview):
    before = _chip_pixels(preview)
    far = QPoint(preview._legend_rect.x(), max(0, preview._legend_rect.y() - 300))
    preview._legend_pointer = far
    assert preview._legend_is_hidden() is False
    preview._repaint_label()
    assert _chip_pixels(preview) == pytest.approx(before, rel=0.15)


# -- the two faults found while designing this ------------------------------

def test_clear_drops_the_previous_charts_patches(preview, tmp_path):
    """`clear()` reset the hover numbers and NOT the painted colours, so after
    loading a new chart the previous chart's measured patches went on painting
    over it."""
    assert preview._patch_overlay, "harness broken: nothing to clear"
    preview.clear()
    assert preview._patch_overlay == {}, (
        "the previous chart's readings would paint over the next one")


def test_the_chip_is_placed_below_the_patches_without_strip_geometry(preview):
    """`_stripe_rects` can be empty while patches are plainly on screen. The
    placement used to consider only strip geometry, so `patch_bottom` stayed at
    the TOP of the sheet and the chip was clamped there — over the column
    letters and the first row."""
    assert not preview._stripe_rects, "harness broken: this needs empty geometry"
    r = preview._legend_rect
    assert r is not None
    assert r.y() > preview.height() * 0.5, (
        f"the chip sits at y={r.y()} of {preview.height()} — at the top, over "
        "the patches, which is the fault this covers")
