"""The split-patch overlay's legend chip must stay on the paper.

Sebastian, 2026-08-13, reviewing the new Measure overlay screenshot: the
"expected ◤ · measured ◢" chip was cut in half by the bottom of the preview.
The width was already clamped ("Keep the whole chip within the paper width so
it never clips"); the height was not — it was clamped to sit BELOW the last
patch row, which on a chart whose patches reach near the bottom edge pushes it
off the paper entirely.
"""
from __future__ import annotations

import inspect
import re

import pytest

from ui.tiff_preview import TiffPreview


@pytest.fixture(scope="module")
def qapp_for_preview():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _legend_block() -> str:
    """From the legend comment to the end of the method — the chip is the last
    thing drawn, so slicing to a fixed length would cut the clamp off."""
    src = inspect.getsource(TiffPreview._draw_cq_overlay)
    return src[src.index("Legend chip"):]


def test_the_chip_is_clamped_on_both_axes():
    """A clamp on one axis only is how this happened: whoever wrote the width
    clamp knew the rule, and the height quietly kept its own."""
    block = _legend_block()
    assert "min(cx, int(img_r - tw))" in block, "the width clamp is gone"
    assert re.search(r"min\(cy, int\(img_b - th - 4\)\)", block), \
        "the chip's height must be clamped inside the paper too"


def test_the_bottom_clamp_comes_last():
    """Order is the whole bug: the paper clamp has to be applied AFTER the
    below-the-patches preference, or the preference overrides it again."""
    block = _legend_block()
    prefer = block.index("patch_bottom + 2")
    clamp = block.index("img_b - th - 4", block.index("patch_bottom + 2"))
    assert clamp > prefer, "the paper clamp must be the last word on cy"


# ---- 2026-08-13: strip rects must never reach past the page --------------
def test_detected_strip_rects_are_clamped_to_the_page(qapp_for_preview):
    """A chart with no engine geometry has its strips DETECTED from the page
    image, and that detector returned a rect ending at 3516 px on a 3508 px
    page. Everything anchored to a strip inherits it: the scan arrow, the
    measured-patch blanking, and the overlay legend, which is where Sebastian
    saw it. The clamp lives in the one setter every source goes through."""
    from PyQt6.QtCore import QRect
    from PyQt6.QtGui import QPixmap

    pv = TiffPreview()
    pv._pixmap = QPixmap(2480, 3508)
    pv.set_stripe_rects([QRect(300, 450, 90, 3066),      # bottom 3516: past it
                         QRect(400, 450, 90, 2800)])     # bottom 3250: fine
    tops = [r.y() + r.height() for r in pv._stripe_rects]
    assert max(tops) <= 3508, f"a strip still reaches past the page: {tops}"
    assert tops[1] == 3250, "a rect that already fits must not be moved"


def test_clamping_survives_a_missing_page(qapp_for_preview):
    """No page loaded yet is normal during setup — the setter must not raise
    or discard the rects, or a chart would arrive with no strips at all."""
    from PyQt6.QtCore import QRect
    pv = TiffPreview()
    pv._pixmap = None
    pv.set_stripe_rects([QRect(0, 0, 10, 10)])
    assert len(pv._stripe_rects) == 1


def test_rects_that_arrive_before_the_page_are_clamped_too(qapp_for_preview):
    """The page image is built by a deferred timer, so strip rects normally
    arrive BEFORE there is a pixmap to measure against. Clamping only in the
    setter therefore did nothing at all in the real call order — found by
    testing the fix rather than trusting it (2026-08-13)."""
    from PyQt6.QtCore import QRect
    from PyQt6.QtGui import QPixmap

    pv = TiffPreview()
    pv._pixmap = None                       # page not loaded yet
    pv.set_stripe_rects([QRect(300, 450, 90, 4000)])     # bottom 4450
    assert pv._stripe_rects[0].height() == 4000, "nothing to clamp against yet"

    pv._pixmap = QPixmap(2480, 3508)        # …the page arrives
    pv._clamp_stripe_rects_to_page()
    r = pv._stripe_rects[0]
    assert r.y() + r.height() <= 3508, "the rect must be trimmed once the page is known"


def test_the_render_applies_the_clamp():
    """Pin the wiring: the clamp has to run where the pixmap is set, not only
    in the setter, or the deferred case above silently returns."""
    import inspect
    src = inspect.getsource(TiffPreview._update_display)
    assert "_clamp_stripe_rects_to_page" in src
