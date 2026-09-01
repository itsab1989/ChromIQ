"""§3 W2 / §6.5: a preset load IS the target's settings — it is not "nothing stored".

Applying a built-in preset seeds the layout panel with the preset's own recipe
and then builds it. Building creates the run and lands the Profile-run bar on
it, which is a target change — so `load_target_settings` runs while that run's
`meta.json` is still empty and takes the §4 S4 branch,
`_open_this_target_on_its_defaults`.

Two of the three things that branch does already stand aside for
`_layout_owned_by_build`: the parameter rows (`_SkipReset`) and every bucket in
`_apply_ui_state` (`built_here`). The third — re-seeding the layout panel from
"Save as Defaults", or from the active per-instrument preset — did not, and it
threw the preset's whole recipe away: paper, margins, minimum patch size and
layout mode. The chart on disk stayed the preset's, so the fault was invisible
until the *second* Generate, which laid the same patches out differently.

The rule this file asserts is §3 W2 ("a preset is loaded → writes Create Chart's
settings for that target"), not §4 S4. §4 S4 still governs every target whose
settings really are nobody's — `test_a_fresh_run_opens_on_its_own_defaults.py`
is the other half of this pair and must stay green.
"""
from __future__ import annotations

import inspect

import pytest

from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager
from core.settings import AppSettings
from ui.tabs.tab_chart import KNUT_PRESETS_BY_KEY, TabChart
from workflow.layout_engine.presets import LayoutRecipe

#: Knut's own chart, and the one his beta-5 report names.
CM84 = ("__chromiq_knut_cm_a4_84p_1page_portrait_w26_0mm_fast_reading_"
        "speed_hand_held__")


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


def _recipe_facts(t):
    """The four values the report measured going stale, plus the grid."""
    r = t._manual_layout_panel.get_recipe()
    return {"paper": r.paper, "layout_mode": r.layout_mode,
            "area_min_patch_mm": r.area_min_patch_mm,
            "margin_left": r.margin_left, "margin_top": r.margin_top,
            "area_cols": r.area_cols, "area_rows": r.area_rows}


def _seed_a_preset(t, key=CM84):
    """Put a built-in preset's recipe on the panel, the way `_seed_knut_preset`
    does for the engine family — and raise the shield its callers raise."""
    p = KNUT_PRESETS_BY_KEY[key]
    assert p.layout_recipe is not None, "this test needs an engine preset"
    t._set_engine_recipe(LayoutRecipe.from_dict(p.layout_recipe))
    t._layout_owned_by_build = True          # what every preset route sets
    return _recipe_facts(t)


def test_the_defaults_opener_keeps_the_preset_the_build_is_using(tab):
    """The whole fault, at the one call that escaped the shield."""
    # Somebody's saved defaults, so `_init_manual_layout_panel` has something
    # to re-seed FROM — which is the shape of the real fault, not a contrivance:
    # without a saved recipe it falls back to the per-instrument preset and the
    # values move anyway.
    other = LayoutRecipe(instrument="i1", paper="A4R")
    other.layout_mode = "patch_first"
    other.area_min_patch_mm = 9.0
    other.margin_left = 21.0
    tab._settings.set("manual_engine_recipe", other.to_dict()
                      if hasattr(other, "to_dict") else other.__dict__)

    before = _seed_a_preset(tab)
    tab._open_this_target_on_its_defaults()
    after = _recipe_facts(tab)

    assert after == before, (
        "applying a preset and letting the build's target change run the "
        "'nothing stored' path discarded the preset's recipe: "
        f"{before} -> {after}")


def test_the_preset_survives_the_whole_load_path(tab, tmp_path):
    """Through `load_target_settings`, not just the opener it calls.

    A store that EXISTS and holds nothing is the branch a freshly created run
    takes, and it is the branch the fault came in through.
    """
    class _EmptyMeta:
        create_chart_settings: dict = {}
        create_chart_ui: dict = {}

    class _EmptyStore:
        dir = tmp_path
        id = "run1"

        def load_meta(self):
            return _EmptyMeta()

        def save_meta(self, meta):      # pragma: no cover - never reached here
            raise AssertionError("the empty-store branch must not write")

    tab._target_settings_store = lambda: _EmptyStore()
    tab._target_settings_key = lambda: ("run1", "profiling")

    before = _seed_a_preset(tab)
    assert tab.load_target_settings() is False, (
        "the premise failed: this must be the 'nothing stored' branch")
    assert _recipe_facts(tab) == before, (
        "the preset's recipe was reset on the way through load_target_settings")


def test_a_fresh_run_with_no_build_still_opens_on_its_defaults(tab):
    """§4 S4 is untouched: with no build owning the layout, the panel resets.

    This is the beta-6 fix for the previous-run leak, restated here so the
    guard above can never be widened into "never reset".
    """
    fresh = _recipe_facts(tab)
    other = LayoutRecipe(instrument="CR30", paper="A4")
    other.layout_mode = "patch_first"
    other.margin_left = 21.0
    tab._set_engine_recipe(other)
    assert _recipe_facts(tab) != fresh, "the premise failed: nothing changed"

    tab._layout_owned_by_build = False        # nothing is building
    tab._open_this_target_on_its_defaults()

    assert _recipe_facts(tab) == fresh, (
        "a genuine fresh run kept the previous run's layout — the beta-6 fix "
        "for the previous-run leak has regressed")


def test_the_guard_is_in_the_opener_and_names_the_flag():
    """The mutation has to land in THIS method.

    `_apply_ui_state` carries a shield of the same name and the same words; a
    check that only greps the module would pass on that one while this one was
    unguarded, which is exactly how the fault survived.
    """
    import ast
    import textwrap
    src = inspect.getsource(TabChart._open_this_target_on_its_defaults)
    tree = ast.parse(textwrap.dedent(src))
    guarded = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        calls = {n.func.attr for n in ast.walk(node.test)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        names = {n.value for n in ast.walk(node.test)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        body_calls = {n.func.attr for n in ast.walk(ast.Module(body=node.body,
                                                               type_ignores=[]))
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        if "_init_manual_layout_panel" in body_calls:
            guarded.append(names | calls)
    assert guarded, ("_init_manual_layout_panel is no longer called from inside "
                     "an `if` in _open_this_target_on_its_defaults — re-point "
                     "this guard at wherever it moved")
    assert all("_layout_owned_by_build" in g for g in guarded), (
        "the layout-panel re-seed in _open_this_target_on_its_defaults runs "
        "without consulting _layout_owned_by_build — a preset's recipe is "
        "thrown away by the target change its own build causes. NOTE: "
        "_apply_ui_state carries a shield of the same name; this check is "
        "deliberately scoped to this method's own syntax tree, because a "
        "module-wide grep passes while this call is unguarded.")
