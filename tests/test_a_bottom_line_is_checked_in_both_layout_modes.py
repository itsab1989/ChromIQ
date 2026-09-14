"""A line too long for the paper runs off in either layout mode.

Found by an adversarial round against v4.3.0-beta.12. `_engine_text_notes`
opened with::

    if r.layout_mode != "area_first":
        return warns + over, over

and everything below it went with the return: the bottom sheet text's WIDTH
check, its height check, and the strip and row indicator checks.

The comment justified it for the labels, and for the labels it is right: in
area-first the label lives inside the margin and a too-small margin pushes it
toward the page edge, while patch-first reserves the band above and below the
patches so it cannot overflow. **None of that is true of the bottom line.** The
paper is the same width in both modes.

Measured by the round, same recipe twice, A4 with a 24 mm clip border on the
right, a 31.5 mm right margin and a typed 13 pt line, ink read off a rendered
sheet with the geometry pinned:

* area-first: one warning, *"It needs 375 mm … 200 mm of it runs off"*;
* patch-first: **no warning at all**, and identical ink, from 4.19 mm to
  210.06 mm on a 210 mm sheet, cut mid-word at the paper's edge.

Patch-first is the default for SpectroScan and CR30, and
`LayoutRecipe.from_dict` falls back to it for any preset dict without the key,
so this was not a corner. `raster.py` still carries a comment asserting "the
panel already warns that the rest runs off"; in that mode it did not.

The guard is scoped to the label checks now. Nothing else changed: every
warning that was unreachable in patch-first before is still unreachable, so the
only new voice is the one that was measured missing.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from workflow.layout_engine.presets import LayoutRecipe    # noqa: E402


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
    yield t
    t.deleteLater()


def _recipe(mode: str) -> LayoutRecipe:
    """The round's own configuration, in one mode or the other."""
    r = LayoutRecipe()
    r.instrument, r.paper = "CM", "A4"
    r.layout_mode, r.use_instrument_margins = mode, False
    r.margin_top = r.margin_bottom = 15.0
    r.margin_left, r.margin_right = 14.0, 31.5
    r.text_edge_top_mm = r.text_edge_mm = r.text_edge_clip_mm = 4.0
    r.chart_text = "X" * 300              # far too long for any sheet
    r.chart_text_size_mm = 13.0 * 25.4 / 72.0
    r.stamp_command = False
    r.show_strip_indicators, r.show_row_indicators = True, False
    r.helper_markers = False
    r.clip_border, r.clip_border_width_mm, r.clip_side = True, 24.0, "right"
    r.clip_content_mode = "text"
    r.randomize, r.seed_fixed, r.seed = True, True, 1234
    return r


def _bottom_warnings(tab, mode):
    from ui.tabs.tab_chart import TabChart
    panel = tab._manual_layout_panel
    panel.set_recipe(_recipe(mode))
    return [w for w in TabChart._engine_text_notes(tab)[1]
            if "along the bottom is too wide" in w]


def test_area_first_still_warns(tab):
    """The control: if this went quiet the test below would pass vacuously."""
    assert _bottom_warnings(tab, "area_first"), (
        "the mode that always warned has stopped")


def test_patch_first_warns_too(tab):
    """MUTATION: put the `return` back and this goes red."""
    assert _bottom_warnings(tab, "patch_first"), (
        "a line 300 characters long runs off the paper and patch-first says "
        "nothing")


def test_both_modes_say_the_same_thing_about_the_same_paper(tab):
    """The width of an A4 does not depend on how the patches were sized."""
    a = _bottom_warnings(tab, "area_first")
    b = _bottom_warnings(tab, "patch_first")
    assert a and b and a[0] == b[0], (a, b)


def test_the_label_checks_stay_area_first_only(tab):
    """THE HALF THAT MUST NOT CHANGE. The strip and row label warnings were
    unreachable in patch-first before and must stay that way: there the band is
    reserved beside the patches and cannot overflow. Widening the fix to them
    would be inventing warnings nobody measured."""
    import ast
    import inspect
    import textwrap
    from ui.tabs.tab_chart import TabChart

    src = inspect.getsource(TabChart._engine_text_notes)
    tree = ast.parse(textwrap.dedent(src))
    # No bare `return` may sit between the guard and the bottom-text block.
    assert 'if r.layout_mode != "area_first":' not in src, (
        "the early return is back, and it takes the bottom text with it")
    assert src.count("_labels_can_overflow") >= 4, (
        "the label checks are no longer guarded, so patch-first now emits "
        "warnings about a band it reserves")
