"""A simulated scan must leave headroom at BOTH ends, or the pack cannot be used.

The "try the hexagonal scanner path yourself" pack (``scripts/
make_hex_scanner_sample.py``) hands the user a stand-in for a 300 dpi scan so
the whole scanner path can be walked with no printer and no scanner. It was
rendered from the chart's own TIFF at the full device range, and a chart TIFF is
device values: a patch asked for at 100 % of a channel is 255 in the file and
one at 0 % is 0.

No scanner produces that, and ``workflow.scan_read_check`` is watching for
exactly it: a patch counts as clipped when any channel reaches
:data:`~workflow.scan_read_check.CLIP_HIGH` or
:data:`~workflow.scan_read_check.CLIP_LOW` on the 0-100 scale, and the build
gate refuses above 15 %. Measured through the real ``scanin``, with the real
per-page ``.cht`` the window prepares, at the window's own 50 % sample area:

===================================  ===============  ================
pack                                 clipped share    the build gate
===================================  ===============  ================
rendered at the full device range    **50 %**         refuses
through the compression              **0 %**          lets it through
===================================  ===============  ================

So the pack's own README walked the user into "Part of this scan has no colour
left in it", and the only advice that message can give is to rescan with the
automatic brightness turned off, which is no help at all to somebody who has no
scanner in the loop. Knut met the same wall on his own 648-patch honeycomb demo
(#182, 2026-09-11): 25 % of a page FULL of patches read at a rail, and every one
of those patches was one the chart itself asks for at 0 % or 100 % of a channel.

This does not rebuild the pack, which costs a chart build apiece. It renders the
one thing that matters -- a block of pure device black beside a block of pure
device white -- puts it through the very function the pack uses, and measures
the middle of each block the way scanin means a sample box.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PIL")
pytest.importorskip("numpy")

from workflow.scan_read_check import CLIP_HIGH, CLIP_LOW   # noqa: E402
from scripts.make_hex_scanner_sample import (              # noqa: E402
    CHART_DPI, simulate_scan)

#: How far inside each rail the interiors must land. Not a bare "under 99.5":
#: a value that merely squeaks past the rail is one blurred edge away from
#: going back over it, and the point is that a scan has room at both ends.
MARGIN = 2.0            # on the 0-100 device scale


def _chart_tif(path, size=240):
    """A chart page with nothing in it but the two extremes: the left half is
    device 0 in every channel, the right half device 255."""
    from PIL import Image
    import numpy as np
    a = np.zeros((size, size, 3), dtype="uint8")
    a[:, size // 2:, :] = 255
    Image.fromarray(a).save(path, dpi=(CHART_DPI, CHART_DPI))
    return path


def _interior_mean(img, box):
    """The mean of a box's middle, as scanin's sample box would read it, on the
    0-100 scale the ``.ti3`` carries."""
    import numpy as np
    x0, y0, x1, y1 = box
    a = np.asarray(img.convert("RGB")).astype(float)[y0:y1, x0:x1]
    return a.reshape(-1, 3).mean(axis=0) * 100.0 / 255.0


def _read_both_ends(tmp_path):
    from PIL import Image
    _chart_tif(tmp_path / "sample.tif")
    out = simulate_scan(tmp_path / "sample", tmp_path / "sample-scan.tif")
    img = Image.open(out)
    w, h = img.width, img.height
    # well inside each half, and well inside the sheet, so the rotation's
    # exposed corners and the blur at the black/white seam are nowhere near it
    q = w // 4
    black = _interior_mean(img, (q - w // 12, h // 2 - h // 12,
                                 q + w // 12, h // 2 + h // 12))
    white = _interior_mean(img, (3 * q - w // 12, h // 2 - h // 12,
                                 3 * q + w // 12, h // 2 + h // 12))
    return black, white


def test_device_black_does_not_come_back_on_the_bottom_rail(tmp_path):
    black, _white = _read_both_ends(tmp_path)
    assert min(black) > CLIP_LOW + MARGIN, (
        f"a patch the chart asks for at 0 % reads {black} on the 0-100 scale, "
        f"at or beside the bottom rail ({CLIP_LOW}); the build gate counts "
        f"that as clipped")


def test_device_white_does_not_come_back_on_the_top_rail(tmp_path):
    _black, white = _read_both_ends(tmp_path)
    assert max(white) < CLIP_HIGH - MARGIN, (
        f"a patch the chart asks for at 100 % reads {white} on the 0-100 "
        f"scale, at or beside the top rail ({CLIP_HIGH}); the build gate "
        f"counts that as clipped")


def test_white_still_sits_high_enough_to_pass_the_under_exposure_check(tmp_path):
    """The other rail of the same wall. `M_SCAN_DARK` fires when the chart's own
    white sits below `scanner_min_highlight` (60), so a compression that made
    the scan safe by making it dark would swap one refusal for another."""
    _black, white = _read_both_ends(tmp_path)
    assert max(white) > 85.0, (
        f"white reads {max(white):.1f} on the 0-100 scale; a scan exposed for "
        f"its target puts it just under the top, and below 60 the window says "
        f"the scan came out too dark")
