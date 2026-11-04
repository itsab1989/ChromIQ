"""4.3.24, review of #214: a newly chosen FD-9 lays out with its OWN values.

H1. Choosing the FD-9 in Manual's layout panel left the patch gaps on the
    previous instrument's 0 mm, so a new FD-9 chart came out with touching
    patches (616 instead of 500 on A4), a layout the README calls physically
    unvalidated. Choosing it now loads the FD-9's stored layout
    (Preferences > Chart Layout), whose built-in default is 8 x 8 mm with
    1 mm gaps both ways; leaving it gives the previous instrument back
    exactly what it had.
M1. Guided's FD-9 read Manual's hidden panel whole: its gaps, but also its
    resolution, randomising and output. It now takes its values the way
    Guided does for every other instrument.
L3. The greyed controls show what applies to an FD-9 chart: its fixed
    margins, no spacers and the patch-first layout.
L4. A non-FD-9 recipe rebuilt from its kwargs is the one 4.3.23 rebuilt.
"""
from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401

import pytest

from tests.test_fd9_chart_creation import ti1
from workflow.fd9.measurement import checked_chart


def _tab(tmp_path, qtbot, **stored):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart

    settings = AppSettings()
    settings._qs = QSettings(str(tmp_path / "isolated.ini"),
                             QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(tmp_path / "projects"))
    for key, value in stored.items():
        settings.set(key, value)
    tab = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    qtbot.addWidget(tab)
    return tab, settings


@pytest.fixture(autouse=True)
def _own_presets(tmp_path, monkeypatch):
    """Presets written here stay in this test."""
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))


def _shown(panel):
    return dict(
        patch=(panel.patch_x.value(), panel.patch_y.value()),
        gaps=(panel.inter_patch.value(), panel.strip_gap.value()),
        margins=tuple(panel.margins[k].value() for k in "trbl"),
        spacer=panel.spacer_mode.currentData(),
        layout=panel.layout_mode.currentData())


def _build(tmp_path, creator, params, name):
    from workflow.layout_engine.chart import build_chart
    kw = creator._engine_kwargs(params)
    source, _ = ti1(tmp_path, rep="RGB", tokens=("R", "G", "B"), count=40)
    result = build_chart(source, tmp_path / name, **kw)
    return checked_chart(result.ti2_path)[1]


def test_manual_fd9_starts_on_its_own_values_and_gives_them_back(
        qapp, qtbot, tmp_path):
    tab, _ = _tab(tmp_path, qtbot)
    tab._user_switch_mode("manual")
    panel = tab._manual_layout_panel
    panel.instr.setCurrentIndex(panel.instr.findData("i1"))
    before = _shown(panel)
    assert before["gaps"] == (0.0, 0.0)          # what the i1Pro leaves there

    panel.instr.setCurrentIndex(panel.instr.findData("FD9"))
    fd9 = _shown(panel)
    assert fd9["patch"] == (8.0, 8.0)
    assert fd9["gaps"] == (1.0, 1.0)             # H1: not the i1Pro's 0 mm
    # L3: the FD-9's own margins (top, right, bottom, left), no spacers, and
    # the layout it always uses.
    assert fd9["margins"] == (38.0, 15.0, 33.0, 15.0)
    assert fd9["spacer"] == "none" and fd9["layout"] == "patch_first"
    for box in (panel.margins["t"], panel.spacer_mode, panel.layout_mode):
        assert not box.isEnabled()
    recipe = panel.get_recipe()
    assert (recipe.inter_patch_mm, recipe.strip_gap_mm) == (1.0, 1.0)

    panel.instr.setCurrentIndex(panel.instr.findData("i1"))
    assert _shown(panel) == before                # unchanged


def test_manual_fd9_takes_its_stored_layout_preset(qapp, qtbot, tmp_path):
    from core.preset_store import save_presets
    from workflow.layout_engine.presets import PresetStore, default_recipe
    tab, settings = _tab(tmp_path, qtbot)
    stored = default_recipe("FD9", "A4")
    stored.patch_w_mm, stored.patch_h_mm = 10.0, 7.0
    stored.inter_patch_mm, stored.strip_gap_mm = 2.0, 0.5
    store = PresetStore()
    store.set(stored)
    save_presets("chart_layout", store.as_named_dict())
    tab._user_switch_mode("manual")
    panel = tab._manual_layout_panel
    panel.instr.setCurrentIndex(panel.instr.findData("i1"))
    panel.paper.setCurrentIndex(panel.paper.findData("A4"))
    panel.instr.setCurrentIndex(panel.instr.findData("FD9"))
    assert _shown(panel)["patch"] == (10.0, 7.0)
    assert _shown(panel)["gaps"] == (2.0, 0.5)


def test_a_loaded_fd9_recipe_keeps_its_own_gaps(qapp, qtbot, tmp_path):
    """A recipe being loaded brings its sizes; only a person choosing the
    FD-9 gets the stored ones."""
    from workflow.layout_engine.presets import LayoutRecipe
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    panel = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(panel)
    panel.set_recipe(LayoutRecipe(instrument="FD9", paper="A4", patch_w_mm=8,
                                  patch_h_mm=6, fd9_gap_mm=None,
                                  inter_patch_mm=0.0, strip_gap_mm=0.0))
    assert _shown(panel)["patch"] == (8.0, 6.0)
    assert _shown(panel)["gaps"] == (0.0, 0.0)


def test_fresh_window_guided_fd9_generates_with_1mm_gaps(
        qapp, qtbot, tmp_path):
    tab, _ = _tab(tmp_path, qtbot)
    tab._user_switch_mode("guided")
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("FD9"))
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4"))
    params = tab._collect_guided()
    assert params.layout_recipe is None
    assert (params.fd9_patch_mm, params.fd9_gap_mm,
            params.fd9_strip_gap_mm) == (8.0, 1.0, 1.0)
    assert tab._creator._engine_total_patches(params) == 500
    layout = _build(tmp_path, tab._creator, params, "guided")
    assert layout["gap_mm"] == [1.0, 1.0]


def test_guided_fd9_never_reads_manuals_panel(qapp, qtbot, tmp_path):
    """M1: whatever Manual's (hidden) panel holds, Guided's FD-9 chart is
    built from Guided's own values and Guided's own resolution."""
    tab, settings = _tab(tmp_path, qtbot, printtarg_dpi=300)
    tab._user_switch_mode("manual")
    panel = tab._manual_layout_panel
    panel.instr.setCurrentIndex(panel.instr.findData("FD9"))
    panel.inter_patch.setValue(0.0)
    panel.strip_gap.setValue(4.0)
    panel.patch_x.setValue(20.0)
    panel.dpi.setValue(150)
    tab._user_switch_mode("guided")
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("FD9"))
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4"))
    params = tab._collect_guided()
    kw = tab._creator._engine_kwargs(params)
    assert (kw["patch_w"], kw.get("inter_patch"), kw.get("strip_gap")) == (
        8.0, 1.0, 1.0)
    assert kw["dpi"] == 300
    assert tab._predicted_patch_count == 500


def test_guided_fd9_uses_the_chart_layout_preset_or_its_saved_defaults(
        qapp, qtbot, tmp_path):
    from core.preset_store import save_presets
    from workflow.layout_engine.presets import PresetStore, default_recipe
    tab, settings = _tab(tmp_path, qtbot)
    stored = default_recipe("FD9", "A4")
    stored.inter_patch_mm, stored.strip_gap_mm = 2.0, 3.0
    store = PresetStore()
    store.set(stored)
    save_presets("chart_layout", store.as_named_dict())
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("FD9"))
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4"))
    p = tab._collect_guided()
    assert (p.fd9_gap_mm, p.fd9_strip_gap_mm) == (2.0, 3.0)
    layout = _build(tmp_path, tab._creator, p, "preset")
    assert layout["gap_mm"] == [3.0, 2.0] or layout["gap_mm"] == [2.0, 3.0]

    # What Save as Defaults stored wins, as for every Guided setting.
    tab2, _ = _tab(tmp_path / "two", qtbot, chart_instrument="FD9",
                   chart_paper="A4", chart_fd9_patch_mm=9.0,
                   chart_fd9_patch_h_mm=7.0, chart_fd9_gap_mm=0.5,
                   chart_fd9_strip_gap_mm=1.5)
    p2 = tab2._collect_guided()
    assert (p2.fd9_patch_mm, p2.fd9_patch_h_mm, p2.fd9_gap_mm,
            p2.fd9_strip_gap_mm) == (9.0, 7.0, 0.5, 1.5)


def test_the_fixed_fields_do_not_change_the_fd9_chart(tmp_path):
    """L3 only changes what the greyed boxes SHOW: an FD-9 chart is the same
    file whatever margins, spacers or layout mode its recipe carries."""
    from dataclasses import replace
    from workflow.layout_engine.chart import build_chart
    from workflow.layout_engine.presets import LayoutRecipe, fd9_fixed_fields
    source, _ = ti1(tmp_path, rep="RGB", tokens=("R", "G", "B"), count=30)
    plain = LayoutRecipe(instrument="FD9", paper="A4", patch_w_mm=8,
                         patch_h_mm=8, fd9_gap_mm=None, inter_patch_mm=1.0,
                         strip_gap_mm=1.0, randomize=False)
    fixed = fd9_fixed_fields(plain)
    assert fixed.margin_top == 38.0 and fixed.spacer_mode == "none"
    out = []
    for name, r in (("a", plain), ("b", replace(fixed, spacer_mode="colored"))):
        res = build_chart(source, tmp_path / name, **r.build_kwargs())
        out.append((res.tiff_paths[0].read_bytes(),
                    checked_chart(res.ti2_path)[1]["rows"]))
    assert out[0] == out[1]


def test_a_preset_from_4323_is_not_reported_as_modified(qapp, qtbot, tmp_path):
    """An equal-gap FD-9 preset written by 4.3.22/4.3.23 (margins 6 mm,
    coloured spacers) is the same layout as the panel shows for it."""
    from core.preset_store import save_presets
    from workflow.layout_engine.presets import LayoutRecipe, PresetStore
    tab, settings = _tab(tmp_path, qtbot)
    old = LayoutRecipe(instrument="FD9", paper="A4", patch_w_mm=8,
                       patch_h_mm=8, fd9_gap_mm=1.0)
    store = PresetStore()
    store.set(old)
    save_presets("chart_layout", store.as_named_dict())
    assert (tab._layout_recipe_values(old)
            == tab._layout_recipe_values(
                LayoutRecipe(instrument="FD9", paper="A4", patch_w_mm=8,
                             patch_h_mm=8, fd9_gap_mm=None,
                             inter_patch_mm=1.0, strip_gap_mm=1.0,
                             spacer_mode="none", margin_top=38.0)))


@pytest.mark.parametrize("inst", ["i1", "SS", "CR30", "CM"])
def test_l4_other_recipes_rebuilt_from_kwargs_keep_the_field_default(inst):
    from workflow.layout_engine.presets import LayoutRecipe
    r = LayoutRecipe(instrument=inst, inter_patch_mm=1.0, strip_gap_mm=2.0)
    assert LayoutRecipe.from_build_kwargs(r.build_kwargs()).fd9_gap_mm == 1.0
