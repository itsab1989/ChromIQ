"""4.3.52: the Measure tab's strip marker on a sheet made outside ChromIQ.

jctay (thread 17845, post 150417, ChromIQ 4.3.49, i1Pro 3): "the progress
arrow moves very slowly behind the active strip". Measured 2026-11-20 on the
sheet he read (the patch-length test sheet 2: a `.ti2` and its TIFF, nine
strips standing apart, "START" and a scale bar in the top left margin, the
strip letters at the BOTTOM): the label-band detector took "START" for the
strip letters and the scale bar under it for the patch block, and laid all
nine strips side by side inside strip A's column, about 10 px apart. The
marker moved "in mini steps" and never left strip A. Sheet 1 the same.

Pinned here: on both sheets strip N's marker rect lies on strip N's printed
column, the marker for every strip is drawn there, and a click on strip N
selects strip N; the charts the old detector got right keep exactly what they
had (the bundled ColorMunki and i1Pro charts), and an FD-9 chart is never
changed by this.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.settings import DEFAULTS  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "jctay_patch_length_sheets"
TRUTH = json.loads((DATA / "strip_columns.json").read_text(encoding="utf-8"))
SHEETS = ["PatchLengthTest_100x150", "PatchLengthTest2_100x150"]
PREBUILT = HERE / "fixtures" / "charts" / "prebuilt" / "pharmacist" / "rgb"


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication(sys.argv)


class _Settings:
    def __init__(self):
        self._d = dict(DEFAULTS)

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


@pytest.fixture
def tab():
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings()
    t = TabMeasure(ArgyllRunner(s), s)
    yield t
    t.close()


def _stage(tmp_path, stem, src=DATA):
    for p in src.glob(stem + "*"):
        if p.suffix.lower() in (".ti2", ".tif", ".ti1"):
            shutil.copy2(p, tmp_path / p.name)
    return tmp_path / f"{stem}.ti2"


@pytest.mark.parametrize("stem", SHEETS)
def test_every_strip_rect_lies_on_its_printed_column(tab, tmp_path, stem):
    tab.set_ti1_path(_stage(tmp_path, stem))
    rects = tab._page_stripe_rects[0]
    truth = TRUTH[stem]
    assert len(rects) == len(truth)
    for r, letter in zip(rects, sorted(truth)):
        x, w, top, bot = truth[letter]
        cx = r.x() + r.width() / 2
        assert x <= cx <= x + w, (letter, r)
        assert abs(r.width() - w) <= 4, (letter, r)
        # the marker hangs above the strip's ink, not over the letters below
        assert abs(r.y() - top) <= 15, (letter, r)
    assert tab._stripe_arrow_mode == "tip"


@pytest.mark.parametrize("stem", SHEETS)
def test_the_marker_moves_to_each_strip(tab, tmp_path, stem):
    tab.set_ti1_path(_stage(tmp_path, stem))
    truth = TRUTH[stem]
    for n, letter in enumerate(sorted(truth)):
        tab._on_stripe_changed(letter)
        pv = tab._preview
        assert pv._active_stripe == n
        r = pv._stripe_rects[pv._active_stripe]
        x, w, _top, _bot = truth[letter]
        assert x <= r.x() + r.width() / 2 <= x + w, (letter, r)
        assert pv._stripe_arrow_mode == "tip"
        assert pv.scan_arrows_shown()


@pytest.mark.parametrize("stem", SHEETS)
def test_a_click_on_strip_n_selects_strip_n(tab, tmp_path, stem):
    tab.set_ti1_path(_stage(tmp_path, stem))
    pv = tab._preview
    pv.set_stripe_click_enabled(True) if hasattr(pv, "set_stripe_click_enabled") \
        else setattr(pv, "_stripe_click_enabled", True)
    truth = TRUTH[stem]
    for n, letter in enumerate(sorted(truth)):
        x, w, top, bot = truth[letter]
        at = (x + w // 2, (top + bot) // 2)
        pv._image_px_at = lambda _pos, _at=at: _at   # the click lands here
        from PyQt6.QtCore import QPoint
        assert pv._stripe_at(QPoint(0, 0)) == n, letter


@pytest.mark.parametrize("rel", [
    "colormunki/a3/tc924/tc924.ti2",
    "colormunki/a4/abw702/abw702.ti2",
    "i1pro/100x150/photocard600/photocard600.ti2",
    "i1pro/130x180/photocard648/photocard648.ti2",
])
def test_a_chart_the_old_detector_got_right_keeps_its_rects(tab, tmp_path, rel):
    """Unchanged to the pixel: the uniform detector's own result, "base"."""
    from core.strip_utils import parse_passes_per_page
    from ui.tabs.tab_measure import _detect_uniform_stripe_rects
    src = PREBUILT / rel
    ti2 = _stage(tmp_path, src.stem, src.parent)
    tab.set_ti1_path(ti2)
    counts = parse_passes_per_page(ti2)
    want = [_detect_uniform_stripe_rects(p, n)
            for p, n in zip(tab._tiff_pages, counts)]
    if not all(want):
        pytest.skip("this chart does not take the uniform path")
    got = tab._page_stripe_rects
    assert [[(r.x(), r.y(), r.width(), r.height()) for r in pg] for pg in got] == \
           [[(r.x(), r.y(), r.width(), r.height()) for r in pg] for pg in want]
    assert tab._stripe_arrow_mode == "base"


def test_an_fd9_chart_is_never_changed_by_this(tab, tmp_path):
    """FD-9 is contributor code: never changed as a side effect. The same
    sheet named an FD-9 chart keeps the 4.3.51 result."""
    from ui.tabs.tab_measure import _detect_uniform_stripe_rects
    stem = "PatchLengthTest2_100x150"
    ti2 = _stage(tmp_path, stem)
    text = ti2.read_text(encoding="latin-1").replace(
        'TARGET_INSTRUMENT "GretagMacbeth i1 Pro"', 'TARGET_INSTRUMENT "FD-9"')
    assert 'TARGET_INSTRUMENT "FD-9"' in text
    ti2.write_text(text, encoding="latin-1")
    tab.set_ti1_path(ti2)
    want = _detect_uniform_stripe_rects(tab._tiff_pages[0], 9)
    got = tab._page_stripe_rects[0]
    assert [(r.x(), r.width()) for r in got] == [(r.x(), r.width()) for r in want]
    assert tab._stripe_arrow_mode == "base"


def test_the_separated_finder_says_nothing_on_touching_strips():
    """printtarg's strips touch: no separate columns, so nothing is offered."""
    from ui.strip_columns import separated_strip_rects
    tif = PREBUILT / "colormunki" / "a3" / "tc924" / "tc924.tif"
    if not tif.is_file():
        tif = next((PREBUILT / "colormunki" / "a3" / "tc924").glob("*.tif"))
    assert separated_strip_rects(tif, 47) == []



def _separated_sheet(path, n, gap_px):
    """A page of *n* strips standing apart by *gap_px* (drawn here, nothing
    of anyone's): 8 patches each, a white margin, no label row."""
    from PIL import Image, ImageDraw
    w, h = 1181, 1772
    im = Image.new("RGB", (w, h), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    x0, x1 = int(w * 0.08), int(w * 0.92)
    pitch = (x1 - x0) / n
    for i in range(n):
        a, b = int(x0 + i * pitch), int(x0 + (i + 1) * pitch) - gap_px
        for j in range(8):
            y = int(h * 0.12) + j * int(h * 0.09)
            dr.rectangle([a, y, b, y + int(h * 0.09) - 1],
                         fill=((37 * i + j * 50) % 200, (90 + j * 20) % 220, (150 + i * 13) % 230))
    im.save(path)


def test_separated_strips_the_old_detector_got_right_keep_its_rects(tab, tmp_path):
    """Review S3 (fix round): the fix is used ONLY where the old result
    disagrees with the separated columns the page shows. A page whose strips
    stand apart by a few pixels, which the old detector reads right, keeps
    the old rects and the "base" arrow: without the uniform_agrees check the
    marker would silently move to "tip" here."""
    from ui.strip_columns import separated_strip_rects, uniform_agrees
    from ui.tabs.tab_measure import _detect_uniform_stripe_rects
    stem = "PatchLengthTest2_100x150"                     # 9 strips, one page
    shutil.copy2(DATA / f"{stem}.ti2", tmp_path / "separated.ti2")
    tif = tmp_path / "separated.tif"
    _separated_sheet(tif, 9, 4)
    old = _detect_uniform_stripe_rects(tif, 9)
    sep = separated_strip_rects(tif, 9)
    # the case this test is about: both find the strips, and they agree
    assert len(old) == 9 and len(sep) == 9 and uniform_agrees(old, sep)
    tab.set_ti1_path(tmp_path / "separated.ti2")
    got = tab._page_stripe_rects[0]
    assert [(r.x(), r.y(), r.width(), r.height()) for r in got] == \
           [(r.x(), r.y(), r.width(), r.height()) for r in old]
    assert tab._stripe_arrow_mode == "base"
