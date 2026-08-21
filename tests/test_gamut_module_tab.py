"""#133 feature B — the FROM PROFILE GAMUT module on the Create Chart tab.

The engine has its own tests (test_gamut_target.py); here the tab is driven:
the module button appears only for a verification target, the no-profile empty
state replaces the options with Generate disabled, Generate routes through the
gamut pipeline, and the adopted chart gets its reference + sidecar marker.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (                     # noqa: E402
    RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from workflow import gamut_target as gt                   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _env(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    # These tests exercise the printtarg path explicitly — since 4.0.0
    # the ChromIQ layout engine is the Manual default (schema 18), so
    # the mode under test is pinned rather than inherited.
    s.set("use_chromiq_layout_engine", False)
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    return s, fm, MeasurementTargetController(fm)


def _chart_tab(s, fm, ctl):
    from ui.tabs.tab_chart import TabChart
    tab = TabChart(ArgyllRunner(s), fm, s, None)
    tab.set_target_controller(ctl)
    return tab


def test_module_button_appears_only_for_a_verification_target(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path)
    tab = _chart_tab(s, fm, ctl)
    assert not tab._gamut_btn.isVisibleTo(tab)

    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert tab._gamut_btn.isVisibleTo(tab)

    # Switching away hides the button AND leaves the module (T-like guard).
    tab._switch_mode("gamut")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert not tab._gamut_btn.isVisibleTo(tab)
    assert tab._mode_name() != "gamut"


def test_no_profile_shows_the_agreed_empty_state(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path)
    tab = _chart_tab(s, fm, ctl)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")
    assert not tab._gamut_grp.isVisibleTo(tab)
    assert tab._gamut_empty_lbl.isVisibleTo(tab)
    assert "needs a finished profile first" in tab._gamut_empty_lbl.text()
    assert not tab._generate_btn.isEnabled()
    # And the Guided/Manual info box shows outside the module.
    tab._switch_mode("manual")
    tab._refresh_gamut_visibility()
    assert tab._verify_noprofile_lbl.isVisibleTo(tab)
    assert "no finished profile in this run yet" in tab._verify_noprofile_lbl.text()


def test_with_a_profile_the_options_show_and_the_info_box_hides(qapp, tmp_path, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.profile_icc.write_bytes(b"icc")
    tab = _chart_tab(s, fm, ctl)
    monkeypatch.setattr(tab, "_gamut_coverage", lambda *a, **k: 5413)
    tab._gamut_master_total = 5960
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")
    assert tab._gamut_grp.isVisibleTo(tab)
    assert not tab._gamut_empty_lbl.isVisibleTo(tab)
    assert not tab._verify_noprofile_lbl.isVisibleTo(tab)
    assert tab._generate_btn.isEnabled()
    tab._update_gamut_count_line()
    text = tab._gamut_count_lbl.text()
    assert "5413" in text and "5960" in text
    assert "8 cube corners" in text


def test_generate_routes_through_the_gamut_pipeline(qapp, tmp_path, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.profile_icc.write_bytes(b"icc")
    tab = _chart_tab(s, fm, ctl)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")

    def fake_select(profile, count, margin, intent, **kw):
        sel = gt.GamutSelection(
            master_version="TEST-r0", master_total=10, in_gamut_total=4,
            requested=count, intent=intent, margin=margin)
        sel.targets = [(i, (50.0, 0.0, 0.0), (10.0 * i, 20.0, 30.0))
                       for i in range(min(count, 4))]
        sel.corners = list(zip(gt.CORNER_DEVICES, gt.CORNER_DEVICES))
        return sel
    monkeypatch.setattr("workflow.gamut_target.select_gamut_targets",
                        fake_select)
    built: list = []
    monkeypatch.setattr(tab, "_generate_from_ti1",
                        lambda ti1, **kw: built.append(Path(ti1)))
    tab._gamut_count_spin.setValue(100)

    tab._on_generate()
    assert built, "gamut mode must route Generate through the gamut pipeline"
    assert built[0].parent == run.cache_dir
    assert built[0].exists()
    sel = tab._pending_gamut_selection
    assert sel is not None and sel.achieved == 4
    # The capped-and-said-so line (§13).
    assert "Only 4 of the requested 100" in tab._log.toPlainText()


def test_reference_and_marker_written_after_adopt(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    ti2 = run.verify_chart_ti2
    ti2.write_text("CTI2\n")
    tab = _chart_tab(s, fm, ctl)

    sel = gt.GamutSelection(
        master_version="TEST-r0", master_total=10, in_gamut_total=2,
        requested=2, intent="absolute", margin="safe")
    sel.targets = [(0, (50.0, 0.0, 0.0), (10.0, 20.0, 30.0))]
    sel.corners = [((100.0, 100.0, 100.0), (100.0, 0.0, 0.0))]
    tab._pending_gamut_selection = sel

    tab._write_gamut_reference_after_adopt(ti2)
    from workflow.verification_print import (STATE_CONVERTED,
                                             chart_conversion_state,
                                             colorimetric_reference_for)
    ref = colorimetric_reference_for(ti2)
    assert ref.exists()
    sidecar = json.loads(run.verify_chart_channels_json.read_text())
    assert sidecar["colorimetric_reference"] == ref.name
    # Feature A's Print tab will now force Raw for this chart.
    assert chart_conversion_state(ti2) == STATE_CONVERTED
    assert tab._pending_gamut_selection is None
    assert "print it exactly as it is" in tab._log.toPlainText()


def test_relayout_restores_the_reference_from_the_cache(qapp, tmp_path):
    """The auto-update preview re-lays out the chart with no fresh selection;
    the adoption step clears the verify files — the reference must come back
    from the module's cached copy, or the chart degrades to the A3c state."""
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    ti2 = run.verify_chart_ti2
    ti2.write_text("CTI2\n")
    tab = _chart_tab(s, fm, ctl)

    sel = gt.GamutSelection(
        master_version="TEST-r0", master_total=10, in_gamut_total=1,
        requested=1, intent="absolute", margin="safe")
    sel.targets = [(0, (50.0, 0.0, 0.0), (10.0, 20.0, 30.0))]
    gt.write_colorimetric_reference(
        sel, run.ensure_cache_dir() / "gamut-target-reference.ti3")

    tab._gamut_active = True
    tab._pending_gamut_selection = None          # a re-layout, not a generate
    tab._write_gamut_reference_after_adopt(ti2)
    from workflow.verification_print import (STATE_CONVERTED,
                                             chart_conversion_state,
                                             colorimetric_reference_for)
    assert colorimetric_reference_for(ti2).exists()
    assert chart_conversion_state(ti2) == STATE_CONVERTED

    # A targen chart replacing a gamut chart must NOT inherit the targets.
    colorimetric_reference_for(ti2).unlink()
    tab._gamut_active = False
    tab._write_gamut_reference_after_adopt(ti2)
    assert not colorimetric_reference_for(ti2).exists()


def test_auto_preview_toggle_shows_in_the_gamut_module(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.profile_icc.write_bytes(b"icc")
    tab = _chart_tab(s, fm, ctl)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")
    assert tab._auto_preview_row_w.isVisibleTo(tab)
    tab._switch_mode("guided")
    assert not tab._auto_preview_row_w.isVisibleTo(tab)


def test_auto_fills_the_manual_pages(qapp, tmp_path, monkeypatch):
    """Auto = per-sheet capacity × the Manual pages spin, minus the 8 corners
    that always ride along; the spin greys and shows the computed number."""
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.profile_icc.write_bytes(b"icc")
    tab = _chart_tab(s, fm, ctl)
    monkeypatch.setattr(tab, "_gamut_per_sheet", lambda: 105)
    monkeypatch.setattr(tab, "_gamut_coverage", lambda *a, **k: 5000)
    tab._gamut_master_total = 5960
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")
    if tab._manual_pages_spin is not None:
        tab._manual_pages_spin.setValue(2)
    tab._gamut_auto_check.setChecked(True)
    assert tab._gamut_effective_count() == 105 * 2 - 8
    tab._update_gamut_count_line()
    assert not tab._gamut_count_spin.isEnabled()
    assert tab._gamut_count_spin.value() == 202
    tab._gamut_auto_check.setChecked(False)
    tab._update_gamut_count_line()
    assert tab._gamut_count_spin.isEnabled()


def test_patch_set_and_preset_buttons_park_in_the_gamut_module(qapp, tmp_path):
    """They bring their OWN patches, which fights the module's purpose
    (Basti, 2026-08-10) — parked while it is active, restored on leaving."""
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.profile_icc.write_bytes(b"icc")
    tab = _chart_tab(s, fm, ctl)
    normal_load_tip = tab._load_ti1_btn.toolTip()
    normal_preset_tip = tab._builtin_preset_btn.toolTip()
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)

    tab._switch_mode("gamut")
    assert not tab._load_ti1_btn.isEnabled()
    assert not tab._builtin_preset_btn.isEnabled()
    assert "FROM PROFILE GAMUT" in tab._load_ti1_btn.toolTip()
    assert "FROM PROFILE GAMUT" in tab._builtin_preset_btn.toolTip()

    tab._switch_mode("manual")
    assert tab._load_ti1_btn.isEnabled()
    assert tab._builtin_preset_btn.isEnabled()
    assert tab._load_ti1_btn.toolTip() == normal_load_tip
    assert tab._builtin_preset_btn.toolTip() == normal_preset_tip


def test_auto_update_assesses_the_verify_chart_not_the_profiling_one(
        qapp, tmp_path, monkeypatch):
    """Regression (Basti, 2026-08-10): with the run's profiling measurement on
    disk, every knob turn answered with the preview-paused note — the auto
    path asked about the profiling chart even though a verification target
    re-lays the VERIFY chart. Free while no dated verification is measured;
    paused again once one is."""
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.profile_icc.write_bytes(b"icc")
    # The profiling side has real work — the exact state that wrongly paused.
    run.measurement_ti3.write_text("CTI3\n")
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text("CTI2\n")
    ti1 = run.verifications_dir / "gamut.ti1"
    ti1.write_text("CTI1\n")
    s.set("auto_update_preview", True)

    tab = _chart_tab(s, fm, ctl)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")
    tab._current_ti1_path = ti1
    built, paused = [], []
    monkeypatch.setattr(tab, "_generate_from_ti1",
                        lambda *a, **k: built.append(1))
    monkeypatch.setattr(tab, "_say_preview_is_paused",
                        lambda: paused.append(1))

    tab._auto_regenerate_preview()
    assert built and not paused, "nothing measured yet — experimenting is free"

    # A measured dated verification with no snapshot has unknown provenance
    # → the §4 pause applies.
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text("CTI3\n")
    built.clear()
    tab._auto_regenerate_preview()
    assert paused and not built

    # Its snapshot matches the live chart → it describes it → still paused.
    from workflow.verify_chart_snapshot import snapshot_chart
    snapshot_chart(v)
    built.clear(); paused.clear()
    tab._auto_regenerate_preview()
    assert paused and not built

    # Generate replaced the live chart (its content changed): the measured
    # date now describes its snapshot, not the live chart — experimenting is
    # free again (Basti: "after hitting generate a working live update").
    run.verify_chart_ti2.write_text("CTI2 regenerated\n")
    built.clear(); paused.clear()
    tab._auto_regenerate_preview()
    assert built and not paused


def test_the_coverage_line_carries_the_percentage(qapp, tmp_path, monkeypatch):
    """The 2026-08-13 audit batch: coverage as a share besides n of N — and
    the label wraps, so the longer line can never widen the tab."""
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.profile_icc.write_bytes(b"icc")
    tab = _chart_tab(s, fm, ctl)
    monkeypatch.setattr(tab, "_gamut_coverage", lambda *a, **k: 5413)
    tab._gamut_master_total = 5960
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")
    tab._update_gamut_count_line()
    assert "(91 %)" in tab._gamut_count_lbl.text()      # round(5413/5960*100)
    assert tab._gamut_count_lbl.wordWrap()


# ---------------------------------------------------------------------------
# #162 — the count defaults to the chart the Manual settings describe
# ---------------------------------------------------------------------------
def _gamut_ready(s, fm, ctl, patches=484):
    """A verification target with a profile, and a Manual chart of *patches*.

    THE REAL ENTRY PATH. Selecting a verification run that has a profile opens
    the module by itself (`_refresh_gamut_visibility`) — calling
    `_switch_mode("gamut")` afterwards is a re-entry the app never performs, and
    an earlier version of these tests only passed because of it.

    The patch count goes through the real targen -f control rather than a stub
    on `_collect_manual`, which also feeds the live command preview.
    """
    run = fm.project().run("run1")
    run.profile_icc.write_bytes(b"icc")
    tab = _chart_tab(s, fm, ctl)
    # IN THE USER'S ORDER. Selecting the run loads that target's Create Chart
    # state, which resets targen -f — so a chart set up before the selection is
    # wiped by it, and a fixture that did so was testing nothing. The run is
    # chosen first, then the chart, exactly as loading a preset does.
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    if patches:
        # Manual's own "Auto patch count" is ON by default and recomputes -f
        # from the layout; a preset turns it off, and so do we.
        if tab._manual_auto_patches_check is not None:
            tab._manual_auto_patches_check.setChecked(False)
        tab._set_manual_value("targen", "-f", patches)
    return tab


def test_the_count_defaults_to_the_chart_manual_describes(qapp, tmp_path):
    """soul-traveller: *"if I select a 484 patch preset, the default value
    should be 484 patches (including the 8 color extremes)"*.

    The box is the count BEFORE the corners — "+ 8" sits beside it — so a
    484-patch Manual chart reads 476 here and totals 484.
    """
    s, fm, ctl = _env(tmp_path)
    s.set("gamut_target_count", 400)          # the stored global he complains of
    tab = _gamut_ready(s, fm, ctl)
    assert tab._mode_name() == "gamut", "the module opens on its own"
    assert tab._gamut_count_spin.value() == 476
    assert tab._gamut_count_spin.value() + 8 == 484


def test_a_count_nobody_chose_does_not_disarm_the_default(qapp, tmp_path):
    """The fault that made the first version of this feature a no-op.

    `_collect_ui_state` files `gamut.count` for every target that is merely
    visited, so every verification target that already exists carries the
    untouched global. Reading "a count is stored" as "the user chose a count"
    disarmed the default on all of them — the change would have done nothing on
    anyone's real data.
    """
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl)
    tab._apply_ui_state({"gamut": {"count": 400}})      # no marker: not a choice
    tab._refresh_gamut_state()
    assert tab._gamut_count_spin.value() == 476


def test_a_count_the_user_typed_is_his(qapp, tmp_path):
    """A default, not an override."""
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl)
    tab._gamut_count_spin.setValue(300)
    tab._set_manual_value("targen", "-f", 918)          # the chart changes under it
    tab._refresh_gamut_state()
    assert tab._gamut_count_spin.value() == 300


def test_a_choice_survives_being_saved_and_loaded(qapp, tmp_path):
    """…and it has to survive as a CHOICE, not merely as a number, or the next
    load cannot tell it from the global."""
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl)
    tab._gamut_count_spin.setValue(300)
    stored = tab._collect_ui_state()
    assert stored["gamut"]["count"] == 300
    assert stored["gamut"]["count_chosen"] is True

    tab._apply_ui_state(stored)
    tab._refresh_gamut_state()
    assert tab._gamut_count_spin.value() == 300


def test_the_default_follows_a_preset_chosen_inside_the_module(qapp, tmp_path):
    """His literal action. The Presets dropdown stays visible inside the module
    and choosing one never switches module, so a default that only fires on
    entry would never fire for him at all."""
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl)
    assert tab._gamut_count_spin.value() == 476
    tab._set_manual_value("targen", "-f", 200)
    assert tab._gamut_count_spin.value() == 192


def test_another_run_while_the_module_is_open_gets_its_own_default(qapp,
                                                                   tmp_path):
    """Selecting another run does not re-enter the module — both automatic
    routes in are guarded by "only if the mode would change" — so the count
    must be re-defaulted where the module's state is refreshed, not only where
    it is opened."""
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl)
    tab._gamut_count_spin.setValue(900)                 # run 1's own choice
    tab._apply_ui_state({})                             # run 2: nothing stored
    tab._set_manual_value("targen", "-f", 484)
    tab._refresh_gamut_state()
    assert tab._gamut_count_spin.value() == 476, (
        "run 2 kept the count from the run just left")


def test_manuals_own_auto_patch_count_still_gives_a_default(qapp, tmp_path,
                                                            monkeypatch):
    """Manual's "Auto" patch count is on by default and leaves targen -f at 0,
    so there would be no chart to match and the box would keep the global."""
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl, patches=0)
    assert tab._manual_auto_patches_check.isChecked(), "Auto is the default"
    monkeypatch.setattr(tab, "_gamut_per_sheet", lambda: 105)
    monkeypatch.setattr(tab, "_gamut_pages", lambda: 2)
    tab._gamut_count_user_set = False
    tab._refresh_gamut_state()
    assert tab._gamut_count_spin.value() == 105 * 2 - 8


def test_the_seed_is_clamped_to_the_box(qapp, tmp_path, monkeypatch):
    """A Manual chart smaller than the box's minimum, or larger than its
    maximum, must not produce a value the box cannot hold."""
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl)
    lo, hi = tab._gamut_count_spin.minimum(), tab._gamut_count_spin.maximum()
    for patches, want in ((9, lo), (100000, hi), (484, 476)):
        monkeypatch.setattr(tab, "_collect_manual",
                            lambda p=patches: type("P", (), {"patches": p})())
        assert tab._gamut_manual_colour_count() == want
    monkeypatch.setattr(tab, "_collect_manual",
                        lambda: type("P", (), {"patches": 0})())
    if tab._manual_auto_patches_check is not None:
        tab._manual_auto_patches_check.setChecked(False)
    assert tab._gamut_manual_colour_count() is None, "no chart, no default"


def test_auto_fill_the_pages_is_untouched(qapp, tmp_path, monkeypatch):
    """The existing Auto computes the sheet's CAPACITY, which is a different
    rule — and with Auto on the box is not the input at all."""
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl)
    monkeypatch.setattr(tab, "_gamut_per_sheet", lambda: 105)
    assert tab._gamut_count_spin.value() == 476
    tab._gamut_auto_check.setChecked(True)
    if tab._manual_pages_spin is not None:
        tab._manual_pages_spin.setValue(2)
    assert tab._gamut_effective_count() == 105 * 2 - 8


def test_choosing_the_module_by_hand_defaults_the_count(qapp, tmp_path):
    """The hand-click path. `_user_switch_mode` goes to `_switch_mode` and
    nowhere near `_refresh_gamut_state`, so the two seeding sites are not
    redundant — and no test clicked the button until a mutation said so.
    """
    s, fm, ctl = _env(tmp_path)
    s.set("gamut_target_count", 400)
    tab = _gamut_ready(s, fm, ctl)
    tab._user_switch_mode("manual")            # leave the module by hand
    tab._gamut_count_spin.setValue(400)        # …and put the global back
    tab._gamut_count_user_set = False          # nobody chose it
    tab._set_manual_value("targen", "-f", 484)  # not in the module: no seed here
    assert tab._gamut_count_spin.value() == 400
    tab._user_switch_mode("gamut")             # click the module button
    assert tab._gamut_count_spin.value() == 476


def _reach(table):
    """A stand-in for the in-gamut query that HONOURS margin and intent.

    The first version of these tests used `lambda *a, **k: 2896`, which
    swallowed both — so a cap that ignored the user's margin and intent passed
    every one of them.
    """
    def _q(profile, margin, intent):
        return table.get((margin, intent))
    return _q


def test_the_default_never_promises_more_than_the_profile_can_print(
        qapp, tmp_path, monkeypatch):
    """Measured against a real profile: a 3000-patch Manual chart put 2992 in
    the box while the line underneath said "Only 2896 can be tested".

    The chart holds `min(count, in-gamut) + 8` whatever the box says, so the
    box and the line contradicted each other with the user having done nothing.
    """
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl, patches=3000)
    monkeypatch.setattr(tab, "_gamut_coverage", _reach({("safe", "absolute"): 2896}))
    tab._gamut_count_user_set = False
    tab._refresh_gamut_state()
    assert tab._gamut_count_spin.value() == 2896


def test_a_wider_reach_raises_the_default_again(qapp, tmp_path, monkeypatch):
    """Margin and intent decide how many colours are in gamut, so the default
    capped by that total has to move when they do.

    The combo is MOVED rather than the slot called by hand: the two `connect`
    lines are the only new wiring, and calling the slot directly leaves them
    untested — a mutation that dropped both survived.
    """
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl, patches=5000)
    monkeypatch.setattr(tab, "_gamut_coverage",
                        _reach({("safe", "absolute"): 2896,
                                ("full", "absolute"): 3805}))
    tab._gamut_count_user_set = False
    tab._refresh_gamut_state()
    assert tab._gamut_count_spin.value() == 2896
    tab._gamut_margin_combo.setCurrentIndex(
        tab._gamut_margin_combo.findData("full"))
    assert tab._gamut_count_spin.value() == 3805


def test_the_cap_bounds_the_chart_and_does_not_replace_it(qapp, tmp_path,
                                                          monkeypatch):
    """A reach ABOVE the Manual chart must change nothing.

    Every earlier test had the reach below the chart, so a cap written as
    "use the reach" instead of "at most the reach" passed them all.
    """
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl, patches=484)
    monkeypatch.setattr(tab, "_gamut_coverage",
                        _reach({("safe", "absolute"): 5000}))
    tab._gamut_count_user_set = False
    tab._refresh_gamut_state()
    assert tab._gamut_count_spin.value() == 476


def test_the_cap_uses_the_printable_total_not_the_reference_set(qapp, tmp_path,
                                                                monkeypatch):
    """5960 reference colours exist; this profile prints 2896 of them. Capping
    at the wrong one of those two numbers is invisible unless they differ."""
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl, patches=5000)
    monkeypatch.setattr(tab, "_gamut_coverage",
                        _reach({("safe", "absolute"): 2896}))
    tab._gamut_master_total = 5960
    tab._gamut_count_user_set = False
    tab._refresh_gamut_state()
    assert tab._gamut_count_spin.value() == 2896


def test_a_profile_that_can_print_nothing_gets_the_smallest_default(
        qapp, tmp_path, monkeypatch):
    """A reach of zero is an ANSWER, not a missing one. Read as "unknown", the
    profile that can print nothing got the largest default of all — reproduced
    on a real .icc at the safe margin with the relative intent."""
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl, patches=3000)
    monkeypatch.setattr(tab, "_gamut_coverage",
                        _reach({("safe", "absolute"): 0}))
    tab._gamut_count_user_set = False
    tab._refresh_gamut_state()
    assert tab._gamut_count_spin.value() == tab._gamut_count_spin.minimum()


def test_auto_fill_the_pages_cannot_promise_missing_colours_either(
        qapp, tmp_path, monkeypatch):
    """The number the user CANNOT correct — Auto greys the box — was the one
    left uncapped: it read 267 beside a line saying "Only 100 can be tested"."""
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl, patches=3000)
    monkeypatch.setattr(tab, "_gamut_coverage",
                        _reach({("safe", "absolute"): 100}))
    monkeypatch.setattr(tab, "_gamut_per_sheet", lambda: 275)
    tab._gamut_auto_check.setChecked(True)
    assert tab._gamut_effective_count() == 100


def test_the_default_falls_back_when_the_reach_is_unknown(qapp, tmp_path,
                                                          monkeypatch):
    """The in-gamut query shells out to xicclu and can fail. It must cost the
    default nothing — the chart Manual describes is still the best answer."""
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl, patches=484)
    monkeypatch.setattr(tab, "_gamut_coverage", _reach({}))
    tab._gamut_count_user_set = False
    tab._refresh_gamut_state()
    assert tab._gamut_count_spin.value() == 476


def test_a_number_the_user_types_may_still_exceed_the_reach(qapp, tmp_path,
                                                            monkeypatch):
    """The cap belongs to the DEFAULT, not to the control. Asking for more than
    the profile can print is allowed — the line says what will happen — and
    lowering it silently would be the override this feature must not become."""
    s, fm, ctl = _env(tmp_path)
    tab = _gamut_ready(s, fm, ctl, patches=484)
    monkeypatch.setattr(tab, "_gamut_coverage", _reach({("safe", "absolute"): 300}))
    tab._gamut_count_spin.setValue(2000)
    tab._refresh_gamut_state()
    assert tab._gamut_count_spin.value() == 2000
