"""The Seed box reports the shuffle the sheet on screen was actually built with.

Basti, 4.1.5-beta.9:

    *"when creating a chart with the layout engine and in the randomisation
    section 'randomise patch order' is active (which is on by default) then
    there is no way to see which seed number was used it seems. when i click
    the new seed button then the seed number field gets a number that is
    reflecting the seed but on initial generation the seed number there is
    always 0 at first or stuck at any other number even when i generate again.
    i think that even when this field is greyed it should reflect the seed
    number of the chart on screen"*

Driven on screen before this file existed
(``scripts/drive_seed_field_shows_the_chart.py``), and both halves of his report
reproduced exactly: two consecutive builds shuffled with 1004140342 and
1778456217 while the box read **0** both times, and only "New seed" ever moved
it.

THE SEED WAS NEVER LOST, ONLY UNREPORTED. ``build_chart`` writes
``RANDOM_START "<seed>"`` into the ``.ti2`` and ``chart_creator`` writes
``layout.seed`` into the chart's ``channels.json``; the same seed does reproduce
the same patch order. What was missing was any way to READ it without opening a
file, and 0 is not a harmless placeholder — it is a valid seed that produces a
real, different shuffle, so the box was not blank, it was WRONG.

The fix is a display, and this file's job is to keep it a display: writing the
built seed into the box must not tick "Use a fixed seed", must not change what
``get_recipe()`` asks the engine for, and must not fire the panel's ``changed``
signal — which drives the live preview and the helper-marker memory, neither of
which should move because a build finished.
"""
from __future__ import annotations

import inspect
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.argyll_runner import ArgyllRunner                  # noqa: E402
from core.file_manager import FileManager                    # noqa: E402
from core.settings import AppSettings                        # noqa: E402
from ui.dialogs.layout_options_panel import LayoutOptionsPanel  # noqa: E402
from ui.tabs.tab_chart import TabChart                       # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe      # noqa: E402


@pytest.fixture()
def panel(qapp):
    p = LayoutOptionsPanel(with_selectors=True)
    p.set_recipe(LayoutRecipe(instrument="i1", paper="A4"))
    yield p
    p.deleteLater()


@pytest.fixture()
def tab(qapp, tmp_path):
    s = AppSettings()
    s.set("custom_output_path", str(tmp_path))
    s.set("use_chromiq_layout_engine", True)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._refresh_manual_command_preview()      # build the engine panel
    if getattr(t, "_manual_layout_panel", None) is None:
        pytest.skip("the engine layout panel is not available in this build")
    yield t
    t.deleteLater()


def _sidecar(tmp_path, *, seed, randomize=True, engine="chromiq", recipe=True):
    """A chart's channels.json, written exactly the way a build writes it."""
    ti2 = tmp_path / "SeedProbe.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    layout: dict = {"engine": engine, "engine_version": 1, "seed": seed}
    if recipe:
        layout["recipe"] = LayoutRecipe(
            instrument="i1", paper="A4", randomize=randomize).to_dict()
    ti2.with_suffix(".channels.json").write_text(
        json.dumps({"layout": layout}), encoding="utf-8")
    return ti2


# ----------------------------------------------------------------------
# 1. The premise — what the box says before anything has been built
# ----------------------------------------------------------------------
def test_zero_is_a_real_seed_and_not_a_placeholder(panel):
    """The box's untouched value is 0, and 0 shuffles a chart like any other
    number — so leaving it there is a false report, not an empty one."""
    from workflow.layout_engine import permutation

    assert panel.seed_spin.value() == 0
    assert panel.seed_spin.minimum() == 0
    a = permutation.location_permutation(64, 0)
    b = permutation.location_permutation(64, 1004140342)
    assert a != b, "0 would have to be inert for the old display to be honest"


def test_a_normal_build_asks_the_engine_for_no_seed_at_all(panel):
    """Why the box could never have been right by accident: with "Use a fixed
    seed" unticked the recipe carries None and the ENGINE picks the number."""
    panel.randomize_cb.setChecked(True)
    panel.fixed_seed_cb.setChecked(False)
    assert panel.get_recipe().seed is None
    assert "seed = permutation.pick_seed()" in inspect.getsource(
        __import__("workflow.layout_engine.chart", fromlist=["x"])), \
        "the engine no longer draws its own seed — this whole file's premise moved"


# ----------------------------------------------------------------------
# 2. The display
# ----------------------------------------------------------------------
def test_the_built_seed_reaches_the_box(panel):
    panel.randomize_cb.setChecked(True)
    panel.fixed_seed_cb.setChecked(False)
    panel.show_built_seed(1004140342)
    assert panel.seed_spin.value() == 1004140342, (
        "the box still does not say which shuffle produced the chart on screen")


def test_it_shows_even_while_the_box_is_greyed(panel):
    """Basti's exact words: *"even when this field is greyed it should reflect
    the seed number of the chart on screen"*."""
    panel.randomize_cb.setChecked(True)
    panel.fixed_seed_cb.setChecked(False)
    assert not panel.seed_spin.isEnabled(), "the premise failed: it is editable"
    panel.show_built_seed(777)
    assert not panel.seed_spin.isEnabled(), "showing a seed must not unlock it"
    assert panel.seed_spin.value() == 777


def test_showing_a_seed_does_not_tick_use_a_fixed_seed(panel):
    """THE RANDOMISATION BEHAVIOUR IS UNTOUCHED. Ticking the box for the user
    would silently pin every later chart to one shuffle — the opposite of the
    default the report describes as correct."""
    panel.randomize_cb.setChecked(True)
    panel.fixed_seed_cb.setChecked(False)
    panel.show_built_seed(1004140342)
    assert not panel.fixed_seed_cb.isChecked()
    assert panel.get_recipe().seed is None, (
        "the next build would now reuse the last chart's shuffle")


def test_a_typed_seed_still_survives_the_display(panel):
    """With a fixed seed the chart is built with what the user typed, so writing
    it back is a no-op that must not disturb the tick."""
    panel.randomize_cb.setChecked(True)
    panel.fixed_seed_cb.setChecked(True)
    panel.seed_spin.setValue(4242)
    panel.show_built_seed(4242)
    assert panel.fixed_seed_cb.isChecked()
    assert panel.get_recipe().seed == 4242


def test_the_display_fires_no_change_signal(panel):
    """``seed_spin.valueChanged`` drives the live preview and the helper-marker
    memory. A build finishing is not the user editing a setting."""
    seen: list[int] = []
    panel.changed.connect(lambda: seen.append(1))
    panel.randomize_cb.setChecked(True)
    panel.fixed_seed_cb.setChecked(False)
    seen.clear()
    panel.show_built_seed(1004140342)
    assert seen == [], f"the display emitted {len(seen)} change signal(s)"


def test_a_fixed_order_chart_gets_no_seed_in_the_box(panel):
    """With "Randomise patch order" off nothing on the sheet was shuffled, so a
    number in the box would describe nothing."""
    panel.randomize_cb.setChecked(False)
    before = panel.seed_spin.value()
    panel.show_built_seed(1004140342)
    assert panel.seed_spin.value() == before


@pytest.mark.parametrize("bad", [None, "not a number", -1, 2_147_483_648])
def test_a_seed_it_cannot_show_leaves_the_box_alone(panel, bad):
    """Out of range or not a number: refuse rather than let Qt clamp it into a
    plausible-looking lie."""
    panel.randomize_cb.setChecked(True)
    panel.seed_spin.setValue(99)
    panel.show_built_seed(bad)
    assert panel.seed_spin.value() == 99


# ----------------------------------------------------------------------
# 3. The wiring — the tab reads the chart's own record, not a variable
# ----------------------------------------------------------------------
def test_the_tab_reads_the_seed_out_of_the_finished_chart(tab, tmp_path):
    ti2 = _sidecar(tmp_path, seed=1778456217)
    tab._manual_layout_panel.randomize_cb.setChecked(True)
    tab._manual_layout_panel.fixed_seed_cb.setChecked(False)
    tab._show_built_seed_in_panel(ti2)
    assert tab._manual_layout_panel.seed_spin.value() == 1778456217


def test_a_fixed_order_chart_on_disk_is_not_reported_as_shuffled(tab, tmp_path):
    ti2 = _sidecar(tmp_path, seed=1778456217, randomize=False)
    tab._manual_layout_panel.seed_spin.setValue(5)
    tab._show_built_seed_in_panel(ti2)
    assert tab._manual_layout_panel.seed_spin.value() == 5


def test_a_printtarg_chart_leaves_the_box_alone(tab, tmp_path):
    """No ChromIQ layout block = printtarg laid this sheet out. The engine's
    Seed box does not describe it."""
    ti2 = _sidecar(tmp_path, seed=99, engine="printtarg")
    tab._manual_layout_panel.seed_spin.setValue(5)
    tab._show_built_seed_in_panel(ti2)
    assert tab._manual_layout_panel.seed_spin.value() == 5


def test_a_chart_with_no_sidecar_at_all_is_survivable(tab, tmp_path):
    (tmp_path / "Gone.ti2").write_text("CTI2\n", encoding="utf-8")
    tab._manual_layout_panel.seed_spin.setValue(5)
    tab._show_built_seed_in_panel(tmp_path / "Gone.ti2")   # must not raise
    tab._show_built_seed_in_panel(None)                    # nor this
    assert tab._manual_layout_panel.seed_spin.value() == 5


def test_every_finished_build_goes_through_it():
    """``_on_generate_finished`` is the one place every generate route ends —
    a fresh build, a rebuild from a .ti1, the gamut route and a verification
    chart that has just been moved under a different stem. Putting the call
    anywhere else would leave some of them silent again."""
    src = inspect.getsource(TabChart._on_generate_finished)
    assert "_show_built_seed_in_panel" in src, (
        "the finished-build path no longer reports the seed it used")


def test_it_is_read_from_the_chart_and_not_from_a_carried_variable():
    """The seed is taken from the sidecar that ended up BESIDE the chart, so a
    verification chart moved into verifications/ under a new stem still reports
    its own number rather than the one the builder happened to be holding."""
    src = inspect.getsource(TabChart._show_built_seed_in_panel)
    assert "channels.json" in src and "from_channels_json" in src
