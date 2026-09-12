"""The bottom sheet text's line is as tall as its TYPE, not as tall as a pitch.

THE FOUR-SIDE AUDIT OF 2026-09-12 MEASURED THIS AND NOTHING WAS DONE WITH IT.
`scripts/drive_182_four_side_symmetry.py` carries the case in its own comments
("bottom sheet text at a TYPED 28 pt … measured ink crosses the 4 mm 'B'
limit", and a B4 block whose note claims a fix that was never built), and the
design record says nothing about it at all.

Reproduced on screen by `scripts/adv1_four_sides_attack.py`, driving the real
window, A4 at 200 dpi, bottom margin 12 mm, "B" 4 mm, one line of sheet text,
the ink measured off the TIFF the app itself wrote against a control sheet with
the text blanked:

| Sheet text Size | the ink's own distance to the bottom of the paper | red notices |
|---|---|---|
| auto | 4.32 mm | 0 |
| 12 pt | 3.17 mm | 0 |
| 18 pt | 0.64 mm | 0 |
| 28 pt | **0.00 mm, and it touches the right edge too** | 0 |

Two things were wrong and they are the same thing:

* `raster.render_page` stacked the lines at a fixed ``px(4.2)`` and anchored
  each by its ASCENDER, so the ink went on down as far as the face takes it.
  The "B" reserve is a limit on this edge exactly as "Clip" is on the sides
  (Knut, 2026-09-12) and it was crossed from about 12 pt up; at 28 pt on A4 the
  line was cut off by the paper edge; and with the settings stamp on as well
  the second line was printed on top of the first.
* `text_edge_fit.sheet_text_overlap` predicted 4.2 mm a line whatever the Size
  was, so the "Measured from Preview" frame stayed silent through all of it.

`raster.sheet_text_line_mm` is the one answer both sides read now: the larger
of the pitch and the face's own ascent plus descent.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_chart import TabChart                    # noqa: E402
from workflow import text_edge_fit as tef                 # noqa: E402
from workflow.layout_engine import geometry, instruments, raster  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe   # noqa: E402
from workflow.layout_engine.ti1_reader import ColorTarget  # noqa: E402

_DEV = (50.0, 50.0, 50.0)
_XYZ = (18.0, 19.0, 21.0)
_TEXT = "ChromIQ adversary one bottom sheet text"
_PAPER_W, _PAPER_H, _DPI = 210.0, 297.0, 200.0
_B_MM = 4.0


def _recipe(size_pt: float, margin_bottom: float = 12.0,
            stamp: bool = False) -> LayoutRecipe:
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = "i1", "A4", "area_first"
    r.dpi = int(_DPI)
    r.clip_border, r.clip_content_mode = False, "off"
    r.margin_top = 20.0
    r.margin_left = r.margin_right = 20.0
    r.margin_bottom = margin_bottom
    r.text_edge_mm = _B_MM
    r.text_edge_top_mm = 8.0
    r.text_edge_clip_mm = 4.0
    r.chart_text = _TEXT
    r.chart_text_size_mm = (size_pt * 25.4 / 72.0) if size_pt else 0.0
    r.stamp_command = stamp
    r.show_strip_indicators, r.show_row_indicators = True, True
    r.helper_markers = False
    r.randomize, r.seed_fixed, r.seed = False, True, 7
    return r


def _page(r: LayoutRecipe, stamp_text: str = ""):
    kw = r.build_kwargs()
    g = instruments.geom_from_build_kwargs(kw)
    lay = geometry.compute(g, _PAPER_W, _PAPER_H, 120)
    target = ColorTarget(color_rep="iRGB",
                         device_fields=["RGB_R", "RGB_G", "RGB_B"],
                         patches=[(_DEV, _XYZ) for _ in range(120)])
    res = raster.render_pages(
        target, lay, g, seed=7, randomize=False,
        paper_w_mm=_PAPER_W, paper_h_mm=_PAPER_H, dpi=int(_DPI),
        chart_text=r.chart_text, chart_text_size_mm=r.chart_text_size_mm,
        stamp_text=stamp_text, text_edge_mm=r.text_edge_mm)
    return g, np.asarray(res.images[0])


def _text_ink_rows(r: LayoutRecipe, stamp_text: str = ""):
    """(first, last) inked row of the sheet text alone, against a control."""
    blank = LayoutRecipe(**{f: getattr(r, f) for f in
                            (x.name for x in r.__dataclass_fields__.values())})
    blank.chart_text = ""
    _g0, a = _page(blank, "")
    _g1, b = _page(r, stamp_text)
    assert a.shape == b.shape
    ga = a.min(axis=2) if a.ndim == 3 else a
    gb = b.min(axis=2) if b.ndim == 3 else b
    d = (ga.astype(np.int32) - gb.astype(np.int32)) > 8
    assert d.any(), "the sheet text left no ink at all"
    ys = np.where(d.any(axis=1))[0]
    return int(ys.min()), int(ys.max()), d.shape[0]


# ---- 1. the helper, and the promise that nothing already drawn moves ------
def test_the_auto_size_still_gives_the_4_2_mm_pitch():
    """Every chart that prints its bottom line at the Size box's "auto" has to
    come out exactly as it did, or this fix is a regression dressed as one."""
    got = raster.sheet_text_line_mm(0.0, "Inter", False, False, _DPI)
    assert got == pytest.approx(tef.SHEET_TEXT_LINE_MM, abs=0.03), (
        f"the auto line box moved to {got:.3f} mm from "
        f"{tef.SHEET_TEXT_LINE_MM} mm")


def test_a_bigger_size_gives_a_bigger_line_box():
    small = raster.sheet_text_line_mm(12.0 * 25.4 / 72.0, "Inter", False,
                                      False, _DPI)
    big = raster.sheet_text_line_mm(28.0 * 25.4 / 72.0, "Inter", False,
                                    False, _DPI)
    assert small > tef.SHEET_TEXT_LINE_MM, small
    assert big > small + 3.0, (small, big)
    # …and it is the FACE's own ascent plus descent, not the em.
    assert big > 28.0 * 25.4 / 72.0, big


# ---- 2. the reserve is a limit on this edge too ---------------------------
@pytest.mark.parametrize("size_pt", [0.0, 12.0, 18.0, 28.0])
def test_the_ink_never_crosses_the_B_reserve(size_pt):
    r = _recipe(size_pt)
    _g, img = _page(r)
    _first, last, height = _text_ink_rows(r)
    keep_px = (height - 1 - last) * 25.4 / _DPI
    assert keep_px >= _B_MM - 0.15, (
        f"at {size_pt or 'auto'} pt the bottom line's ink is {keep_px:.2f} mm "
        f"from the paper edge, inside the {_B_MM:.1f} mm “B” reserve")


def test_the_line_is_not_cut_off_by_the_paper_edge():
    """28 pt on A4 printed the line straight off the bottom of the sheet."""
    r = _recipe(28.0)
    _first, last, height = _text_ink_rows(r)
    assert last < height - 2, (
        "the bottom line's ink reaches the last row of the sheet, so it is "
        "being cut by the paper edge")


def test_two_lines_are_not_printed_on_top_of_each_other():
    """The sheet text and the settings stamp are two lines at one pitch."""
    r = _recipe(28.0, margin_bottom=40.0, stamp=True)
    first, last, _h = _text_ink_rows(r, stamp_text="printtarg -i i1 -h")
    span_mm = (last - first + 1) * 25.4 / _DPI
    one = raster.sheet_text_line_mm(r.chart_text_size_mm, r.chart_text_font,
                                    False, False, _DPI)
    assert span_mm > one + 2.0, (
        f"two lines of 28 pt type span {span_mm:.2f} mm, and one line's box "
        f"alone is {one:.2f} mm, so they are stacked on top of each other")


# ---- 3. and the panel says so ---------------------------------------------
class _Btn:
    def __init__(self, on=True):
        self._on = on

    def isChecked(self):
        return self._on


class _Edit:
    def text(self):
        return ""


class _Settings:
    def get(self, key, default=None):
        return True if key == "use_chromiq_layout_engine" else default


class _Tab:
    _manual_btn = _Btn()
    _manual_layout_panel = object()
    _settings = _Settings()

    def __init__(self, recipe):
        self._recipe = recipe
        self._manual_chart_notes_edit = _Edit()
        self._manual_stamp_cmd_check = _Btn(False)

    def _current_layout_recipe(self):
        return self._recipe


def _bottom_notice(r) -> str:
    lines = [w for w in TabChart._engine_text_notes(_Tab(r))[1]
             if "sheet text along the bottom" in w]
    return lines[0] if lines else ""


def test_the_panel_is_silent_while_the_line_really_does_fit():
    assert _bottom_notice(_recipe(0.0)) == "", (
        "a warning on a chart whose bottom line fits is how people learn to "
        "ignore warnings")


@pytest.mark.parametrize("size_pt,margin", [(18.0, 10.0), (28.0, 12.0)])
def test_the_panel_warns_about_a_line_too_big_for_its_margin(size_pt, margin):
    """The line's own box is bigger than the paper between "B" and the patches.

    Both of these pass `sheet_text_overlap`'s old 4.2 mm test with room to
    spare, so before the fix the panel said nothing about either.
    """
    assert margin - _B_MM > tef.SHEET_TEXT_LINE_MM, (
        "pick a margin the 4.2 mm pitch fits inside, or this proves nothing")
    msg = _bottom_notice(_recipe(size_pt, margin_bottom=margin))
    assert msg, (
        f"a {size_pt:.0f} pt bottom line on a {margin:.0f} mm bottom margin "
        f"raised no warning at all")
    want = raster.sheet_text_line_mm(size_pt * 25.4 / 72.0, "Inter", False,
                                     False, _DPI)
    assert f"needs {want:.1f} mm" in msg, (
        f"the message does not name the {want:.1f} mm the line really takes:"
        f"\n  {msg}")
    assert "needs 4.2 mm" not in msg, (
        "the message is still quoting the 4.2 mm pitch:\n  " + msg)


def test_the_panel_and_the_renderer_read_one_function():
    """The prediction is only worth something while it is the same number."""
    import inspect
    src = inspect.getsource(raster.render_pages)
    assert "sheet_text_line_mm(chart_text_size_mm" in src, (
        "the renderer has gone back to a line height of its own")
    panel = inspect.getsource(TabChart._engine_text_notes)
    assert "sheet_text_line_mm" in panel, (
        "the panel is predicting the bottom line with a number of its own")
