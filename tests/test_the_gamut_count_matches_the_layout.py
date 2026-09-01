"""The patches-per-sheet the gamut box quotes must be the layout's own.

`_gamut_per_sheet` called `_engine_capacity` with the PRINTTARG widgets while
the engine lays Manual mode out from the recipe panel — so it ignored the patch
size, the margins and the clip border and answered 550 for every layout, against
a real 88 to 540. Its docstring said "engine-exact". Measured wrong in 8 of 8
layouts by a challenge round; on a 20 mm-patch chart it was out by 6.25x.

Same family as the Guided estimate that promised 368 patches on a sheet holding
345: a number quoted to the user, derived from a different source than the thing
it describes.
"""
import pytest

from workflow.layout_engine import geometry, instruments, papers


@pytest.fixture()
def tab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("use_chromiq_layout_engine", True)
    return TabChart(ArgyllRunner(s), FileManager(s), s)


def _what_the_layout_holds(tab) -> int:
    r = tab._manual_layout_panel.get_recipe()
    geom = instruments.geom_from_build_kwargs(r.build_kwargs())
    w_mm, h_mm = papers.dimensions_mm(r.paper)
    return int(geometry.patches_per_sheet(geom, w_mm, h_mm))


def test_the_stock_layout_is_quoted_correctly(tab):
    assert tab._gamut_per_sheet() == _what_the_layout_holds(tab)


def test_it_follows_the_margins(tab):
    panel = tab._manual_layout_panel
    if not getattr(panel, "margins", None):
        pytest.skip("no margin boxes in this panel shape")
    for k in ("t", "r", "b", "l"):
        panel.margins[k].setValue(20.0)
    assert tab._gamut_per_sheet() == _what_the_layout_holds(tab), (
        "the quoted count ignored a 20 mm margin change")


def test_it_follows_the_row_indicators(tab):
    panel = tab._manual_layout_panel
    before = tab._gamut_per_sheet()
    panel.show_row_indicators.click()
    after = tab._gamut_per_sheet()
    assert after == _what_the_layout_holds(tab)
    assert after != before, (
        "switching the row indicators on cost patch area but the quoted count "
        "did not move")


def test_it_follows_the_patch_size(tab):
    panel = tab._manual_layout_panel
    box = getattr(panel, "patch_w", None) or getattr(panel, "pw", None)
    if box is None or not hasattr(box, "setValue"):
        pytest.skip("no patch-size box in this panel shape")
    box.setValue(20.0)
    assert tab._gamut_per_sheet() == _what_the_layout_holds(tab), (
        "a 20 mm patch was quoted at the default layout's count")
