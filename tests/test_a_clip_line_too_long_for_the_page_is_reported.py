"""A clip-border line that runs off the page must say so.

Knut, 2026-09-13:

    "Also, when clip-border is on and a custom text is defined, which is too
     long for the page hight and available space, no warning is given, and the
     long text only disappears out of page in both ends."

`clip_text_squeeze` asks whether the stacked lines fit ACROSS the band. Nothing
asked whether one of them fits ALONG it. `raster._vtext` centres the line on a
canvas the length of the clip area (`cx = height/2`, anchor "mm") and the canvas
crops it, so what does not fit is lost at BOTH ends, with no ellipsis and
nothing in the log.

Measured on A4 with a 26 mm band and T = B = 4.0, on the sheets the app wrote:

    298 chars, Size auto    drawn at the 7 pt floor   needs 330.5 mm, 21.5 off each end
    the same, Size 9 pt     no shrink at all          needs 434.8 mm, 73.6 off each end
    41 chars                fits                      nothing lost

and the crop on the sheet matched the prediction character for character: the
auto case begins "t: this sheet belongs..." with the first 18 characters gone
and ends "...print log sheet stapled" with the last 21 gone.

**The rule existed and was never wired.** `text_edge_fit.page_text_height_mm` is
Knut's own *"page height minus T and minus B ... whichever is smallest"*, and a
grep over `ui/`, `workflow/` and `tests/` found exactly one caller: its own unit
test.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from workflow import text_edge_fit as tef  # noqa: E402


def test_the_predicate_allows_exactly_what_the_renderer_allows():
    """`raster._vtext` keeps a 0.995 hair off the ends, and so must this.

    A second copy of that number in the panel is a second copy that can drift,
    which is why it is named once, here.
    """
    from workflow.layout_engine import raster

    assert tef.CLIP_LINE_FILL == 0.995
    src = raster._vtext.__doc__ or ""
    del src
    import inspect
    body = inspect.getsource(raster._vtext)
    assert "THICK, LEN = 0.98, 0.995" in body, (
        "the renderer's fill factors moved; `CLIP_LINE_FILL` has to follow")

    assert tef.clip_line_overflow(100.0, 99.0) is None
    assert tef.clip_line_overflow(100.0, 99.5) is None      # inside the hair
    over = tef.clip_line_overflow(100.0, 120.0)
    assert over is not None
    assert over.available_mm == pytest.approx(99.5)
    assert over.overlap_mm == pytest.approx(20.5)


def test_nothing_is_reported_for_a_line_that_fits():
    assert tef.clip_line_overflow(289.0, 100.0) is None
    assert tef.clip_line_overflow(0.0, 0.0) is None


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", True)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    return t


_UNIT = ("Clip border content: this sheet belongs to the studio profiling set "
         "for the Canon Pro-1000 and must be kept with the print log sheet. ")
_SHORT = "Studio profiling set, keep with the log"


def _long_enough(tab) -> str:
    """A line that really does run off THIS chart's page, at the auto floor.

    Asked of `raster.sheet_text_width_mm`, which is the function that draws it,
    rather than hard-coded: the face depends on the recipe's font family and on
    what Pillow can find, and a length that overflows with Inter loaded fits
    with the fallback. The first version of this test typed 298 characters,
    measured 330.5 mm on the driver's chart and 227.9 mm here, and went quiet.
    """
    from workflow.layout_engine import geometry as gm
    from workflow.layout_engine import instruments, papers, raster

    r = tab._current_layout_recipe()
    geom = instruments.geom_from_build_kwargs(r.build_kwargs())
    _pw, ph = papers.dimensions_mm(str(r.paper))
    area = gm.clip_area_mm(geom, ph, _pw, 1, 0.0)
    assert area is not None, "this chart has no clip band to overflow"
    room = float(area[3]) * tef.CLIP_LINE_FILL
    for n in range(1, 12):
        text = (_UNIT * n).strip()
        if raster.sheet_text_width_mm(
                [text], tef.AUTO_SHRINK_FLOOR_PT * 25.4 / 72.0,
                str(getattr(r, "clip_text_font", "") or ""),
                dpi=float(getattr(r, "dpi", 300) or 300)) > room:
            return text
    pytest.skip("no line length overflows this chart's band")


def _apply(tab, text: str, size_mm: float = 0.0):
    panel = tab._manual_layout_panel
    r = panel.get_recipe()
    r.clip_border = True
    r.clip_side = "left"
    r.clip_content_mode = "text"
    r.clip_text = text
    r.clip_text_size_mm = size_mm
    r.clip_border_width_mm = 26.0
    r.margin_left = 30.0
    panel.set_recipe(r)
    from ui.tabs.tab_chart import TabChart
    return [w for w in TabChart._engine_text_notes(tab)[1]
            if "too long for the page" in w]


def test_a_long_line_at_the_auto_floor_is_reported(tab):
    msgs = _apply(tab, _long_enough(tab))
    assert msgs, "the line runs off both ends of the page and nothing is said"
    m = msgs[0]
    assert "cut at both ends" in m, m
    assert "at each end" in m, m
    assert "“Clip-border content”" in m, "the size box is not named: " + m
    # It must NOT borrow the Sheet-text floor sentence: a different frame.
    assert "“Sheet text”" not in m, m


def test_a_typed_size_never_shrinks_so_it_loses_more(tab):
    line = _long_enough(tab)
    auto = _apply(tab, line)
    typed = _apply(tab, line, size_mm=9.0 * 25.4 / 72.0)
    assert auto and typed
    import re

    def off(msgs):
        return float(re.search(r"so (\d+) mm of it runs off",
                               msgs[0]).group(1))

    assert off(typed) > off(auto), (
        "a typed 9 pt is bigger than the 7 pt floor and must lose more:\n"
        f"auto {off(auto)} typed {off(typed)}")


def test_a_line_that_fits_says_nothing(tab):
    assert not _apply(tab, _SHORT), (
        "a clip text that fits is being warned about")
