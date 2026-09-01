"""§4 S4: *"factory settings, or the saved defaults — never the last run's."*

A run with nothing stored used to keep the previous run's layout on screen and
then write it into its own `meta.json`, permanently, as though the person had
chosen it. Two ways in — a run whose `meta.json` does not exist yet, and one
whose `create_chart_settings` is empty — and only the second reset anything;
neither reset the layout panel, which is where the instrument, the mode and
both indicator checkboxes live.
"""
from __future__ import annotations

import pytest

from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager
from core.settings import AppSettings
from ui.tabs.tab_chart import TabChart
from workflow.layout_engine.presets import LayoutRecipe


@pytest.fixture
def tab(qapp, tmp_path):
    s = AppSettings()
    s.set("custom_output_path", str(tmp_path))
    s.set("use_chromiq_layout_engine", True)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._refresh_manual_command_preview()      # build the engine panel
    if getattr(t, "_manual_layout_panel", None) is None:
        pytest.skip("the engine layout panel is not available in this build")
    return t


def _selection(t):
    r = t._manual_layout_panel.get_recipe()
    return (r.instrument, r.paper, r.show_row_indicators,
            r.show_strip_indicators, r.layout_mode)


def test_the_opener_puts_the_layout_panel_back_on_its_defaults(tab):
    fresh = _selection(tab)

    # …what the previous run left there.
    other = LayoutRecipe(instrument="CR30", paper="A4")
    other.layout_mode = "patch_first"
    other.show_row_indicators = False
    other.show_strip_indicators = True
    tab._set_engine_recipe(other)
    assert _selection(tab) != fresh, "the premise failed: nothing was changed"

    tab._open_this_target_on_its_defaults()

    assert _selection(tab) == fresh, (
        "a run with nothing stored opened on the PREVIOUS run's layout: "
        f"{_selection(tab)} instead of {fresh}")


def test_the_empty_store_branch_goes_through_the_opener():
    """A store that exists and holds nothing must reset. The other branch —
    no store at all — must NOT: that is also a target with no project, where
    the person's typed values have nowhere else to live."""
    import inspect
    src = inspect.getsource(TabChart.load_target_settings)
    src = "\n".join(l for l in src.splitlines()
                    if not l.lstrip().startswith("#"))
    assert src.count("_open_this_target_on_its_defaults()") == 1, (
        "the 'a store exists and holds nothing' path does not open the target "
        "on its defaults — which is how the previous run's layout leaked in")
