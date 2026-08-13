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

from ui.tiff_preview import TiffPreview


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
