"""A queued live re-render must never replace the chart a build just made.

Basti, 2026-08-16, on the first ColorMunki preset picked in a session: *"it
loaded and immediately reloaded without any spacers."*

The live preview ("Update the preview automatically") re-lays out **the chart
currently on screen** — ``_current_ti1_path``. Picking a built-in preset changes
the layout options first, which queues that re-render against the OLD chart, and
only then builds the preset's own patch set. If the 450 ms timer fired before
the build finished, the preset the user had just picked was replaced by the
previous chart's patches re-flowed into the preset's layout: a chart that looked
wrong and belonged to nothing. It was a race, which is why it came and went.

The rule these tests pin: **starting a real build cancels any queued re-render.**
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("auto_update_preview", True)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    return t


def test_starting_a_build_from_a_patch_set_drops_a_queued_re_render(tab, tmp_path):
    ti1 = tmp_path / "chart.ti1"
    ti1.write_text("CTI1\n")                     # never reached: the guard fires first
    tab._auto_preview_timer.start(450)
    assert tab._auto_preview_timer.isActive()

    # Decline the §4 question, so the call returns straight after the cancel and
    # nothing is actually built — the cancel must already have happened.
    tab._confirm_displacing_results = lambda *a, **k: False
    tab._generate_from_ti1(ti1)
    assert not tab._auto_preview_timer.isActive(), (
        "a queued live re-render survived the start of a real build — it would "
        "re-lay-out whatever chart was on screen before")


def test_the_generate_button_drops_a_queued_re_render(tab):
    tab._auto_preview_timer.start(450)
    tab._confirm_displacing_results = lambda *a, **k: False
    tab._on_generate()
    assert not tab._auto_preview_timer.isActive()


def test_a_running_process_still_wins(tab, tmp_path):
    """The is_running guard comes first: with a process running nothing starts,
    so a queued re-render is left alone (it re-checks is_running itself)."""
    class _Busy:
        is_running = True
    tab._runner = _Busy()
    tab._auto_preview_timer.start(450)
    tab._generate_from_ti1(tmp_path / "nope.ti1")
    assert tab._auto_preview_timer.isActive()


def test_a_build_in_flight_is_seen_even_with_no_argyll_process(tab):
    """The second half of the fault, and the half that actually bit.

    A chart laid out by the ChromIQ layout engine runs no external tool, so
    ``_runner.is_running`` is False for its whole duration. The preview used only
    that guard, so while an engine build was in the air it queued — and then ran —
    a competing re-layout of the chart from *before* that build. With a preset
    that changes the grid (say 17 columns to 38) the patches came back about half
    as wide: the old patch set poured into the new preset's layout.
    """
    tab._generate_btn.setEnabled(False)          # a build is in the air
    assert tab._chart_build_in_flight()
    tab._generate_btn.setEnabled(True)           # _on_generate_finished
    assert not tab._chart_build_in_flight()


def test_no_re_render_is_queued_while_a_build_is_in_flight(tab, tmp_path):
    ti1 = tmp_path / "chart.ti1"
    ti1.write_text("CTI1\n")
    tab._current_ti1_path = ti1
    tab._last_auto_sig = "something else"        # the layout "changed"
    tab._generate_btn.setEnabled(False)
    tab._maybe_schedule_auto_preview()
    assert not tab._auto_preview_timer.isActive()


def test_a_queued_re_render_that_fires_late_still_declines(tab, tmp_path):
    """Belt and braces: even if a timer somehow survives to fire mid-build, the
    re-render itself declines rather than racing the build."""
    ti1 = tmp_path / "chart.ti1"
    ti1.write_text("CTI1\n")
    tab._current_ti1_path = ti1
    tab._generate_btn.setEnabled(False)
    built: list = []
    tab._generate_from_ti1 = lambda *a, **k: built.append(a)
    tab._auto_regenerate_preview()
    assert not built


def test_the_targets_stored_layout_does_not_overwrite_the_one_being_built(tab):
    """The cause Basti's own log named.

    Building a chart makes the run its own, and creating or re-aligning that run
    fires the target-switch handler — which loads the run's *stored* Create Chart
    state straight over the layout the build is using. His log, picking the
    84-patch Hand Held preset::

        chart build (user): chart.ti1, A4, 7x12 grid, margins … L6.0
        layout panel set_recipe [load_target_settings ← _apply_ui_state]  ×4
        chart build (live preview): …, 17x12 grid, margins … L14.0

    The chart on disk was right; the panel had been put back to the previous
    preset's layout, and the live preview then rebuilt from the panel.
    """
    from ui.tabs.tab_chart import KNUT_PRESETS
    from workflow.layout_engine.presets import LayoutRecipe
    # His two charts, verbatim: the Hand Held one being built (7 columns, 6 mm
    # left margin) and the one the run had stored (17 columns, 14 mm).
    hand_held = next(p for p in KNUT_PRESETS if p.slug.startswith("cm_a4_84p"))
    stored = next(p for p in KNUT_PRESETS if p.slug.startswith("cm_a4_204p"))
    panel = tab._manual_layout_panel
    being_built = LayoutRecipe.from_dict(hand_held.layout_recipe)
    stored_ui = {"engine_recipe": dict(stored.layout_recipe)}

    panel.set_recipe(being_built)
    tab._generate_btn.setEnabled(False)          # …and that build is in flight
    tab._apply_ui_state(stored_ui)
    kept = panel.get_recipe().to_dict()
    assert kept["area_cols"] == 7 and kept["margin_left"] == 6.0, (
        "the run's stored layout overwrote the one the build is using")

    # With no build running, the target's own stored layout wins again — that
    # is the per-target settings model working as designed.
    tab._generate_btn.setEnabled(True)
    tab._layout_owned_by_build = False
    tab._apply_ui_state(stored_ui)
    back = panel.get_recipe().to_dict()
    assert back["area_cols"] == 17 and back["margin_left"] == 14.0


def test_the_protection_outlasts_the_build_itself(tab):
    """The window that actually bit, traced on Basti's own settings::

        7.475  build starts    7 columns, 6 mm left margin  (the preset)
        7.605  build finished
        7.9-8.6 the run's stored settings load — 17 columns, 14 mm
        9.358  the live preview rebuilds the chart from THAT

    Every reverting load lands AFTER the build has finished, because the run the
    build creates does not resolve until the target-change handler has run once
    — so the write that would file the new layout cannot succeed until then. A
    guard tied to "a build is running" is therefore always too short: the layout
    a build used has to stay authoritative until that first handler pass.
    """
    from ui.tabs.tab_chart import KNUT_PRESETS
    from workflow.layout_engine.presets import LayoutRecipe
    hand_held = next(p for p in KNUT_PRESETS if p.slug.startswith("cm_a4_84p"))
    stored = next(p for p in KNUT_PRESETS if p.slug.startswith("cm_a4_204p"))
    panel = tab._manual_layout_panel
    panel.set_recipe(LayoutRecipe.from_dict(hand_held.layout_recipe))

    tab._layout_owned_by_build = True        # the build set this on its way in
    tab._generate_btn.setEnabled(True)       # …and has already finished
    assert not tab._chart_build_in_flight()

    tab._apply_ui_state({"engine_recipe": dict(stored.layout_recipe)})
    kept = panel.get_recipe().to_dict()
    assert kept["area_cols"] == 7 and kept["margin_left"] == 6.0, (
        "the run's older stored layout came back after the build finished")


def test_the_protection_cannot_latch_on(tab):
    """It must clear itself, or a run's stored layout would never load again.

    The target-change handler clears it unconditionally, on the same pass that
    files the built layout — so at worst one load is skipped, never all of them.
    """
    tab._layout_owned_by_build = True
    ctl = getattr(tab, "_target_ctl", None)
    if ctl is None:
        pytest.skip("no target controller on this tab")
    tab._on_target_changed()
    assert tab._layout_owned_by_build is False


def test_picking_a_builtin_preset_leaves_no_timer_running(tab, monkeypatch):
    """End to end: after a preset has been applied, nothing is queued that could
    still overwrite it."""
    from ui.tabs.tab_chart import KNUT_PRESETS, TabChart
    preset = next(p for p in KNUT_PRESETS if p.slug.startswith("cm_a4_204p"))
    built: list[Path] = []

    def fake_build(self, ti1_path, *, ask=True):
        # Same order the real method uses: guard, then cancel, then build.
        self._cancel_pending_auto_preview()
        built.append(ti1_path)
    monkeypatch.setattr(TabChart, "_generate_from_ti1", fake_build)

    tab._auto_preview_timer.start(450)           # something was already queued
    tab._apply_knut_preset(preset.key, "Probe")
    assert built and built[0].name == "chart.ti1"
    assert not tab._auto_preview_timer.isActive()
