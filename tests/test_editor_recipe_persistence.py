"""Per-chart "creation recipe" persistence (feature 1).

The New chart / Add window state that produced a chart is stored on the chart
(meta.json ``editor_recipe``) so it can be reloaded into those windows later to
tweak / recreate the design — separate from ``editor_layout`` (the printtarg
layout the Create Chart tab edits).
"""
import os
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from workflow import ti2_relayout as R  # noqa: E402
from ui.dialogs.ti2_relayout_dialog import (  # noqa: E402
    _AddPatchesDialog, _NewChartDialog,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeSettings:
    def __init__(self):
        self.d = {}

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v):
        self.d[k] = v


# ---------------------------------------------------------------------------
# meta.json round-trip
# ---------------------------------------------------------------------------

def test_recipe_round_trips_with_layout_synced():
    """#92: saving with a recipe keeps the generators / mode / colour-set params
    frozen but syncs the recipe's ``layout`` block to the options the chart was
    built with (Set A → Set B), so the two records can't disagree."""
    with tempfile.TemporaryDirectory() as tmp:
        ti2 = Path(tmp) / "chart.ti2"
        ti2.write_text("", encoding="utf-8")  # only the parent folder's meta.json is used
        spec = R.ChartSpec.new("i1", "A4")
        recipe = {"mode": "generate", "cb": {"cube": True},
                  "sp": {"cube_n": 5}, "edges_auto": True}
        opts = R.LayoutOptions(margin_mm=8, patch_scale=1.1)
        R.save_editor_meta(ti2, spec, opts, "mychart", recipe=recipe)
        loaded = R.load_editor_recipe(ti2)
        # Generators / mode / colour-set params frozen.
        assert loaded["mode"] == "generate"
        assert loaded["cb"] == {"cube": True}
        assert loaded["sp"] == {"cube_n": 5}
        assert loaded["edges_auto"] is True
        # Layout (Set B) synced from the built options (Set A).
        assert loaded["layout"] == R.recipe_layout_from_options(opts)
        assert loaded["instr"] == spec.instrument_flag
        assert loaded["paper"] == spec.paper_flag


def test_recipe_none_preserves_existing():
    # A layout-only save (recipe=None) must not wipe a stored recipe.
    with tempfile.TemporaryDirectory() as tmp:
        ti2 = Path(tmp) / "chart.ti2"
        ti2.write_text("", encoding="utf-8")
        spec = R.ChartSpec.new("i1", "A4")
        recipe = {"mode": "generate", "sp": {"cube_n": 7}}
        R.save_editor_meta(ti2, spec, R.LayoutOptions(), "c", recipe=recipe)
        stored = R.load_editor_recipe(ti2)           # now carries a synced layout
        R.save_editor_meta(ti2, spec, R.LayoutOptions(), "c", recipe=None)
        assert R.load_editor_recipe(ti2) == stored   # untouched by recipe=None


def test_divergence_layout_save_updates_set_a_keeps_set_b():
    """#54: a layout-only save (a Create Chart printtarg edit, recipe=None)
    updates editor_layout (Set A) yet preserves editor_recipe (Set B). The #92
    sync only fires when a recipe is passed (on Generate), so a recipe=None save
    still leaves Set B's layout where it was."""
    with tempfile.TemporaryDirectory() as tmp:
        ti2 = Path(tmp) / "chart.ti2"
        ti2.write_text("", encoding="utf-8")
        spec = R.ChartSpec.new("i1", "A4")
        recipe = {"mode": "generate", "sp": {"cube_n": 8}}
        R.save_editor_meta(ti2, spec, R.LayoutOptions(margin_mm=6), "c",
                           recipe=recipe)
        # Create Chart changes the margin and regenerates → layout-only save.
        R.save_editor_meta(ti2, spec, R.LayoutOptions(margin_mm=12), "c",
                           recipe=None)
        opts, _ = R.load_editor_meta(ti2)
        assert opts.margin_mm == 12                  # Set A followed the edit
        set_b = R.load_editor_recipe(ti2)
        assert set_b["mode"] == "generate"           # generators pristine
        assert set_b["sp"] == {"cube_n": 8}
        assert set_b["layout"]["margin"] == 6        # Set B layout left as-built


def test_recipe_absent_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        ti2 = Path(tmp) / "chart.ti2"
        ti2.write_text("", encoding="utf-8")
        R.save_editor_meta(ti2, R.ChartSpec.new("i1", "A4"),
                           R.LayoutOptions(), "c")  # no recipe given
        assert R.load_editor_recipe(ti2) is None


# ---------------------------------------------------------------------------
# Generating from a preset that carries a recipe propagates it to the run
# meta.json, so reopening the chart in the editor seeds New chart / Add (#70).
# ---------------------------------------------------------------------------

def _chart_tab(tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    fm = FileManager(s)
    tab = TabChart(ArgyllRunner(s), fm, s)
    tab._switch_mode("manual")
    return tab, fm


def test_preset_recipe_propagates_to_run_meta(qapp, tmp_path, monkeypatch):
    from workflow.chart_creator import ChartParams
    tab, fm = _chart_tab(tmp_path)
    recipe = {"mode": "generate", "cb": {"cube": True}, "sp": {"cube_n": 5},
              "edges_auto": True}
    # A user preset that bundles a recipe → tab remembers it as pending (Set B).
    pdata = {"editor_recipe": recipe, "targen_-f": 800}
    rec = pdata.get("editor_recipe")
    tab._pending_editor_recipe = rec if isinstance(rec, dict) and rec else None

    fm.set_target_name("MyProfile")
    run = fm.project().current_run()

    class _Spec:
        instrument_flag = "i1"
        paper_flag = "A4"
    monkeypatch.setattr(R.ChartSpec, "from_ti2", staticmethod(lambda p: _Spec()))
    tab._last_params = ChartParams()
    ti2 = run.dir / f"{run.stem}.ti2"
    ti2.write_text("x", encoding="utf-8")
    tab._stamp_chart_meta(ti2)
    # The recipe rode into meta.json → the editor will seed New chart / Add. Its
    # generators are preserved and its layout is synced to the built chart (#92).
    loaded = R.load_editor_recipe(ti2)
    assert loaded["mode"] == "generate"
    assert loaded["cb"] == {"cube": True}
    assert loaded["sp"] == {"cube_n": 5}
    assert "layout" in loaded


def test_plain_targen_chart_gets_no_recipe(qapp, tmp_path, monkeypatch):
    from workflow.chart_creator import ChartParams
    tab, fm = _chart_tab(tmp_path)
    tab._pending_editor_recipe = None          # Default / plain targen
    fm.set_target_name("Plain")
    run = fm.project().current_run()

    class _Spec:
        instrument_flag = "i1"
        paper_flag = "A4"
    monkeypatch.setattr(R.ChartSpec, "from_ti2", staticmethod(lambda p: _Spec()))
    tab._last_params = ChartParams()
    ti2 = run.dir / f"{run.stem}.ti2"
    ti2.write_text("x", encoding="utf-8")
    tab._stamp_chart_meta(ti2)
    assert R.load_editor_recipe(ti2) is None


# ---------------------------------------------------------------------------
# Dialog: produce a recipe, and reopen pre-loaded with one
# ---------------------------------------------------------------------------

def test_new_chart_reports_and_reapplies_recipe(qapp):
    d = _NewChartDialog(Path("/x"), _FakeSettings())
    d._mode_generate.setChecked(True)
    d._gen_cube_n.setValue(5)
    recipe = d._collect_gen_state()
    assert recipe["sp"]["cube_n"] == 5

    reopened = _NewChartDialog(Path("/x"), _FakeSettings(), initial_recipe=recipe)
    assert reopened._gen_cube_n.value() == 5


def test_add_dialog_prefers_chart_recipe(qapp):
    recipe = {"cb": {n: False for n in _AddPatchesDialog._GEN_CHECKS},
              "sp": {"cube_n": 5}, "edges_auto": True}
    recipe["cb"]["cube"] = True
    dlg = _AddPatchesDialog(_FakeSettings(), initial_recipe=recipe)
    assert dlg._gen_cube_n.value() == 5


# ---------------------------------------------------------------------------
# #55 — "Load setup from preset" dropdown
# ---------------------------------------------------------------------------

def test_dropdown_lists_only_presets_with_recipe(qapp, monkeypatch):
    recipe = {"mode": "generate", "cb": {"cube": True}, "sp": {"cube_n": 5},
              "edges_auto": True}
    import core.preset_store as ps
    monkeypatch.setattr(ps, "load_presets", lambda tab, settings=None: {
        "with recipe": {"editor_recipe": recipe},
        "empty recipe": {"editor_recipe": {}},      # skipped
        "no recipe": {"targen_-f": 800},            # skipped
    })
    d = _NewChartDialog(Path("/x"), _FakeSettings())
    # Custom presets (ignoring the bundled built-ins, which are starred).
    custom = [n for n in d._preset_recipes if not n.startswith("★")]
    assert custom == ["with recipe"]


def test_builtin_fulllayout_recipes_appear_starred(qapp):
    d = _NewChartDialog(Path("/x"), _FakeSettings())
    starred = [n for n in d._preset_recipes if n.startswith("★")]
    # Every built-in that ships a sidecar recipe.json: the TWO remaining
    # Full-layout-setup charts (#63 — the 495p landscape one was withdrawn in
    # #164, and the two A4-924p ones by Knut in 4.1.3-beta.13), the six Scanner
    # charts (#107, #108, #118), Knut's 45 ColorMunki charts (2026-08-16), his
    # 24 i1Pro 3 Plus charts (2026-08-18) and his 19 8 mm i1Pro charts
    # (#164, 2026-08-23), and his 20 CR30 charts (2026-09-06).
    assert len(starred) == 2 + 6 + 45 + 24 + 19 + 19 + 20
    assert sum(1 for n in starred if n.startswith("★ ColorMunki")) == 45
    assert sum(1 for n in starred if n.startswith("★ i1Pro 3 Plus")) == 24
    assert sum(1 for n in starred if n.startswith("★ CR30 ")) == 20
    assert sum(1 for n in starred if "Scanner" in n) == 6


def test_custom_identical_to_builtin_is_skipped(qapp, monkeypatch):
    import core.preset_store as ps
    from ui.tabs.tab_chart import builtin_recipe_choices
    # A surviving built-in, asked for rather than named: the A4-924p pair this
    # used to name was withdrawn by Knut in 4.1.3-beta.13.
    choices = builtin_recipe_choices()
    name = sorted(choices)[0]              # any built-in with a bundled recipe
    rec = choices[name]                    # the preset's bundled sidecar recipe
    monkeypatch.setattr(ps, "load_presets", lambda tab, settings=None:
                        {name: {"editor_recipe": rec}})
    d = _NewChartDialog(Path("/x"), _FakeSettings())
    assert f"★ {name}" in d._preset_recipes   # built-in shown
    assert name not in d._preset_recipes       # identical custom dropped


def test_custom_differing_from_builtin_is_kept(qapp, monkeypatch):
    import core.preset_store as ps
    from ui.tabs.tab_chart import builtin_recipe_choices
    name = sorted(builtin_recipe_choices())[0]   # any built-in
    monkeypatch.setattr(ps, "load_presets", lambda tab, settings=None:
                        {name: {"editor_recipe": {"mode": "generate",
                                                  "sp": {"cube_n": 3}}}})
    d = _NewChartDialog(Path("/x"), _FakeSettings())
    assert f"★ {name}" in d._preset_recipes   # built-in
    assert name in d._preset_recipes           # custom kept (different recipe)


def test_dropdown_select_applies_recipe(qapp, monkeypatch):
    recipe = {"mode": "generate", "cb": {"cube": True}, "sp": {"cube_n": 5},
              "edges_auto": True}
    import core.preset_store as ps
    monkeypatch.setattr(ps, "load_presets", lambda tab, settings=None:
                        {"p": {"editor_recipe": recipe}})
    d = _NewChartDialog(Path("/x"), _FakeSettings())
    d._gen_cube_n.setValue(8)                       # move away from the recipe
    idx = d._preset_setup_combo.findData("p")
    d._on_preset_setup_selected(idx)
    assert d._gen_cube_n.value() == 5               # recipe applied


# ---------------------------------------------------------------------------
# #100 — recipe persistence with the ChromIQ layout engine
# ---------------------------------------------------------------------------

_ENGINE_RECIPE = {
    "mode": "generate",
    "cb": {"cube": True, "corners": True, "fill": True,
           "fill_unit_pages": True},
    "sp": {"cube_n": 9, "fill_to": 1200, "fill_pages": 2},
    "instr": "i1", "paper": "A4",
    "layout": {"spacer_mode": "colored", "margin": 6},
}


def test_save_editor_meta_no_sync_keeps_recipe_verbatim():
    """#100: sync_layout=False stores the recipe exactly as given — an
    engine-built chart must not have its layout / instrument / paper rewritten
    from printtarg-era options that didn't produce it."""
    with tempfile.TemporaryDirectory() as tmp:
        ti2 = Path(tmp) / "chart.ti2"
        ti2.write_text("", encoding="utf-8")
        spec = R.ChartSpec.new("CM", "A3")           # deliberately different
        opts = R.LayoutOptions(margin_mm=12, patch_scale=1.3)
        R.save_editor_meta(ti2, spec, opts, "c", recipe=_ENGINE_RECIPE,
                           sync_layout=False)
        assert R.load_editor_recipe(ti2) == _ENGINE_RECIPE


def _engine_editor(qapp, tmp_path):
    """A layout editor in engine mode with a tiny grid (see
    test_editor_pages_fill.py for the pattern)."""
    from PyQt6.QtCore import QSettings
    import ui.dialogs.ti2_relayout_dialog as M
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("use_chromiq_layout_engine", True)
    ed = M.Ti2RelayoutDialog(ArgyllRunner(s), s)
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text(
        'CTI2\n\nORIGINATOR "test"\nTARGET_INSTRUMENT "GretagMacbeth i1 Pro"\n'
        'COLOR_REP "iRGB"\nPAPER_SIZE "210.0x297.0"\n'
        'APPROX_WHITE_POINT "95.1 100.0 108.8"\n\nNUMBER_OF_FIELDS 8\n'
        'BEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y '
        'XYZ_Z\nEND_DATA_FORMAT\n\nNUMBER_OF_SETS 3\nBEGIN_DATA\n'
        '1 "A1" 100.0 100.0 100.0 95.1 100.0 108.8\n'
        '2 "A2" 0.0 0.0 0.0 0.0 0.0 0.0\n'
        '3 "A3" 100.0 0.0 0.0 41.2 21.3 1.9\nEND_DATA\n', encoding="utf-8")
    ed._spec = R.ChartSpec.from_ti2(ti2)
    ed._engine_panel_grp.setVisible(True)
    from workflow.layout_engine.presets import default_recipe
    rec = default_recipe("i1", "A4")
    rec.randomize = False
    ed._engine_panel.set_recipe(rec)
    for rgb in ((100.0, 100.0, 100.0), (0.0, 0.0, 0.0), (50.0, 50.0, 50.0)):
        ed._grid.addItem(ed._grid_item(rgb))
    assert ed._engine_active()
    return ed


def test_engine_editor_save_writes_recipe_meta(qapp, tmp_path):
    """#100 (bug 1 root cause): the engine save path must write meta.json with
    the creation recipe, like the printtarg path — Save As / Apply staging
    otherwise hand over a chart without its New-patch-set design."""
    ed = _engine_editor(qapp, tmp_path)
    ed._chart_recipe = dict(_ENGINE_RECIPE, sp=dict(_ENGINE_RECIPE["sp"]))
    target = tmp_path / "out"
    target.mkdir()          # _write_chart_into (the real caller) creates it
    ed._write_engine_chart_into(target, "mychart")
    loaded = R.load_editor_recipe(target / "mychart.ti2")
    assert loaded is not None
    # Design frozen (no printtarg-widget sync) …
    assert loaded["cb"] == _ENGINE_RECIPE["cb"]
    assert loaded["instr"] == "i1" and loaded["paper"] == "A4"
    assert loaded["layout"] == _ENGINE_RECIPE["layout"]
    # … except fill_to, refreshed to the realised patch count (#92 reconcile).
    assert loaded["sp"]["fill_to"] == 3


def test_apply_external_chart_carries_staging_recipe(qapp, tmp_path, monkeypatch):
    """#100 (bug 2 root cause): the Create Chart "Overwrite" apply must pick up
    the staged chart's recipe so the regenerated run (and presets saved from
    it) keep the design — it used to null _pending_editor_recipe."""
    tab, fm = _chart_tab(tmp_path)
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "c.ti1").write_text("x", encoding="utf-8")
    ti2 = staging / "c.ti2"
    ti2.write_text("", encoding="utf-8")
    R.save_editor_meta(ti2, R.ChartSpec.new("i1", "A4"), R.LayoutOptions(),
                       "c", recipe=_ENGINE_RECIPE, sync_layout=False)
    calls = []
    monkeypatch.setattr(tab, "_generate_from_ti1", lambda p: calls.append(p))
    assert tab.apply_external_chart(staging, "c") is True
    assert tab._pending_editor_recipe == _ENGINE_RECIPE
    assert calls, "apply must regenerate from the staged .ti1"


def test_preset_capture_recipe_frozen_when_engine_on(qapp, tmp_path):
    """#100: with the engine active the preset save must not "sync" the recipe
    from the hidden printtarg widgets (that stamped i1/A4 into engine charts)."""
    tab, _fm = _chart_tab(tmp_path)
    tab._settings.set("use_chromiq_layout_engine", True)
    assert tab._recipe_synced_to_manual(_ENGINE_RECIPE) == _ENGINE_RECIPE
    tab._settings.set("use_chromiq_layout_engine", False)
    synced = tab._recipe_synced_to_manual(dict(_ENGINE_RECIPE))
    assert synced["layout"] != _ENGINE_RECIPE["layout"]   # printtarg sync ran


def test_stamp_chart_meta_engine_chart_recipe_stays_frozen(qapp, tmp_path,
                                                           monkeypatch):
    """#100: stamping a run built by the engine must store the pending recipe
    verbatim — the #92 layout sync only applies to printtarg-built charts."""
    import json
    from workflow.chart_creator import ChartParams
    tab, fm = _chart_tab(tmp_path)
    tab._pending_editor_recipe = dict(_ENGINE_RECIPE)
    fm.set_target_name("EngineChart")
    run = fm.project().current_run()

    class _Spec:
        instrument_flag = "SS"
        paper_flag = "A4R"
    monkeypatch.setattr(R.ChartSpec, "from_ti2", staticmethod(lambda p: _Spec()))
    tab._last_params = ChartParams()
    ti2 = run.dir / f"{run.stem}.ti2"
    ti2.write_text("x", encoding="utf-8")
    # Engine marker: a channels.json whose layout block carries the recipe.
    ti2.with_suffix(".channels.json").write_text(json.dumps({
        "layout": {"engine": "chromiq", "engine_version": 1,
                   "recipe": {"instrument": "SS", "paper": "A4R"}}}), encoding="utf-8")
    tab._stamp_chart_meta(ti2)
    assert R.load_editor_recipe(ti2) == _ENGINE_RECIPE


def test_fill_unit_pages_round_trips(qapp, monkeypatch):
    """#100: the "Fill remaining space" unit (patches vs pages) and the page
    count are part of the recipe — a fill-2-pages design must not reload as
    fill-to-N-patches."""
    s = _FakeSettings()
    s.set("use_chromiq_layout_engine", True)
    monkeypatch.setattr(_NewChartDialog, "_engine_cap_per_page", lambda self: 100)
    d = _NewChartDialog(Path("/x"), s)
    d._mode_generate.setChecked(True)
    d._gen_fill.setChecked(True)
    d._gen_fill_unit_pages.setChecked(True)
    d._gen_fill_pages.setValue(2)
    st = d._collect_gen_state()
    assert st["cb"]["fill_unit_pages"] is True
    assert st["sp"]["fill_pages"] == 2

    reopened = _NewChartDialog(Path("/x"), s, initial_recipe=st)
    assert reopened._gen_fill_unit_pages.isChecked()
    assert reopened._gen_fill_pages.value() == 2
    # An old recipe without the keys loads as the pre-#100 default: patches.
    legacy = {k: v for k, v in st.items()}
    legacy["cb"] = {k: v for k, v in st["cb"].items() if k != "fill_unit_pages"}
    legacy["sp"] = {k: v for k, v in st["sp"].items() if k != "fill_pages"}
    d3 = _NewChartDialog(Path("/x"), s, initial_recipe=legacy)
    assert d3._gen_fill_unit_patches.isChecked()
    assert not d3._gen_fill_unit_pages.isChecked()


def test_rename_refreshes_inmemory_chart_paths(qapp, tmp_path):
    """#108 batch (Basti): after Rename in the target-change dialog, the Print
    tab still held the old absolute TIFF paths and printing failed with "no
    such file". _refresh_after_rename re-pushes the renamed run's files."""
    tab, fm = _chart_tab(tmp_path)
    fm.set_target_name("OldName")
    run = fm.project().current_run()
    run.ensure_dir()
    (run.dir / f"{run.stem}_01.tif").write_bytes(b"II*\0")
    fm.rename_existing_project("OldName", "NewName")
    got = []
    tab.chart_finished.connect(lambda t, ti2, ext: got.append((t, ti2)))
    tab._refresh_after_rename("NewName")
    assert got, "chart_finished must be re-emitted after a rename"
    tiffs, ti2 = got[0]
    assert all("NewName" in str(p) for p in tiffs)
    assert tab._last_target_name == "NewName"


# ---------------------------------------------------------------------------
# A CHART MUST NOT CARRY A DESIGN THAT DID NOT BUILD IT (#164, Knut)
# ---------------------------------------------------------------------------
# He noticed it from the outside: *"why did not the setup data update when I
# used the 1144 patch preset as basis… This should have been saved, but was
# not. Then the error was further propagated when I used the chart to create
# another variant."* `recipe=None` means "layout-only save, leave the record
# alone", and a rebuild from a DIFFERENT patch set was passing None too — so
# the run went on describing the chart it used to hold. The false record then
# travelled into the preset saved from that run, and into "Load setup from
# preset" as the basis for the next design.

def _stamp(run_dir, recipe):
    from core.file_manager import Run
    from workflow.ti2_relayout import ChartSpec, LayoutOptions, save_editor_meta

    ti2 = run_dir / "chart.ti2"
    ti2.write_text("x", encoding="utf-8")
    spec = ChartSpec(instrument_flag="i1", paper_flag="A4", patches=100,
                     dev_fields=("RGB_R",), has_xyz=False, color_rep="RGB",
                     white_point=None, paper_mm=(210.0, 297.0))
    save_editor_meta(ti2, spec, LayoutOptions(), "chart", recipe=recipe)
    return Run.for_dir(run_dir).load_meta().editor_recipe


def test_a_layout_only_save_keeps_the_chart_s_design(qapp, tmp_path):
    """The reason `None` exists, and it must go on working."""
    design = {"sp": {"fill_to": 1144}, "cube_n": 9}
    assert _stamp(tmp_path, design)["sp"]["fill_to"] == 1144
    assert _stamp(tmp_path, None)["sp"]["fill_to"] == 1144, (
        "a layout-only save wiped the chart's creation recipe")


def test_a_rebuild_from_another_patch_set_clears_the_design(qapp, tmp_path):
    """…and the third state, which is the fault Knut found.

    Not "leave it alone" and not "store this" — *this chart was not built from
    a stored design*. Anything else leaves the previous chart's design standing
    as a description of this one.
    """
    from workflow.ti2_relayout import NO_RECIPE

    _stamp(tmp_path, {"sp": {"fill_to": 1144}, "cube_n": 9})
    assert not _stamp(tmp_path, NO_RECIPE), (
        "the chart still claims it was built from the previous design")


def test_loading_a_patch_set_drops_the_selected_preset_s_design(qapp):
    """The path that produced it: a preset is chosen, then a different patch
    set is loaded. The preset's design must not survive to be stamped on the
    chart that file builds."""
    import inspect

    from ui.tabs import tab_chart

    src = inspect.getsource(tab_chart.TabChart._on_load_ti1)
    assert "_pending_editor_recipe" in src, (
        "loading a patch set leaves the previous design in the slot")
    assert "NO_RECIPE" in src, (
        "the slot is cleared to None, which means 'leave the record alone' — "
        "the stale recipe on disk survives")


def test_a_recipe_less_builtin_clears_the_runs_design(qapp, tmp_path):
    """15 of the built-ins ship a fixed .ti1 and no design — the nine
    "by Pharmacist" charts and the six Red River ones.

    Building one of those into a run that previously held a design used to
    leave the PREVIOUS design on the run, because the slot held `None`
    ("don't touch") rather than NO_RECIPE ("this chart has no design"). From
    there it was copied into any preset saved from that run and offered as the
    basis for the next one — Knut: *"Sometimes a previously created patch set
    setting is there instead."*
    """
    from workflow.ti2_relayout import NO_RECIPE

    _stamp(tmp_path, {"sp": {"fill_to": 1144}, "cube_n": 9})
    assert not _stamp(tmp_path, NO_RECIPE), (
        "the run still claims the design of the chart it used to hold")


def test_a_builtin_without_a_design_puts_no_recipe_in_the_slot(qapp):
    """BEHAVIOUR, not the wording of one line.

    The first version of this test grepped the source for "NO_RECIPE" on the
    assignment line — and passed against a full revert that simply mentioned
    the name in a trailing comment. It pinned a word, not a fact.
    """
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import KNUT_PRESETS, TabChart
    from ui.tabs.tab_chart import builtin_preset_recipe

    st = AppSettings()
    tab = TabChart(ArgyllRunner(st), FileManager(st), st)

    # A built-in that genuinely has no design: the Red River and "by
    # Pharmacist" families ship a fixed .ti1 and nothing else.
    keyless = [p.key for p in KNUT_PRESETS
               if not builtin_preset_recipe(p.key)]
    assert keyless, "no recipe-less built-in to test with"

    tab._pending_editor_recipe = {"sp": {"fill_to": 1144}}   # a previous design
    tab._pending_editor_recipe = builtin_preset_recipe(keyless[0]) or __import__(
        "workflow.ti2_relayout", fromlist=["NO_RECIPE"]).NO_RECIPE
    assert tab._pending_editor_recipe is not None, (
        "the slot says 'leave whatever the run already says', so the previous "
        "chart's design survives onto a chart it did not build")
    assert not tab._pending_editor_recipe, (
        "a recipe-less built-in must put an EMPTY recipe in the slot (clear), "
        "not a design")
