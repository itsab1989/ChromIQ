"""Preset panel locks + override checkboxes (Create Chart → Manual).

Selecting a preset that supplies a fixed patch set (.ti1) or a fixed layout
(prebuilt-files) greys the matching parameter panel. An override checkbox above
each panel lets the user unlock it:

  • ti1 preset      → only targen greyed; one "Edit patch recipe" box.
  • prebuilt preset → both greyed; "Edit patch recipe" + "Edit page layout".

Unlocking + editing changes what "Generate Chart" does (fresh targen / re-lay
the bundled patches / copy verbatim). These tests pin the wiring without
shelling out to ArgyllCMS (generation is stubbed).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.argyll_env import argyll_bin_dir, argyll_tool

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Argyll is needed only by the applied-editor-chart tests that stage a real
# chart; they skip cleanly when it isn't installed.
_BIN_DIR = argyll_bin_dir()
_HAS_ARGYLL = argyll_tool("printtarg") is not None

# A minimal but valid .ti2 the layout editor can lay out (mirrors the fixture
# in test_ti2_relayout.py).
_TI2 = """CTI2

ORIGINATOR "test"
TARGET_INSTRUMENT "GretagMacbeth i1 Pro"
COLOR_REP "iRGB"
PAPER_SIZE "210.0x297.0"
APPROX_WHITE_POINT "95.1 100.0 108.8"

NUMBER_OF_FIELDS 8
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 4
BEGIN_DATA
1 "A1" 100.0 100.0 100.0 95.1 100.0 108.8
2 "A2" 0.0 0.0 0.0 0.0 0.0 0.0
3 "A3" 100.0 0.0 0.0 41.2 21.3 1.9
4 "B1" 0.0 0.0 100.0 18.0 7.2 95.0
END_DATA
"""

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_chart import (  # noqa: E402
    KNUT_PRESET_KEYS,
    PREBUILT_PRESETS,
    TabChart,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "chromiq_test.ini"), QSettings.Format.IniFormat)
    # Keep every project ChromIQ writes inside the test's tmp dir, never the
    # real ~/ChromIQ — otherwise the applied-chart tests pollute the home folder
    # (and a rerun would trip the name-collision dialog into a modal hang).
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


def _make_tab(qapp, settings) -> TabChart:
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    return t


def _targen_enabled(tab) -> bool:
    return all(w.isEnabled() for w in tab._manual_targen_content)


def _printtarg_enabled(tab) -> bool:
    return all(w.isEnabled() for w in tab._manual_printtarg_content)


# ---------------------------------------------------------------------------
# Default state: nothing locked
# ---------------------------------------------------------------------------

def test_default_no_locks(qapp, settings):
    tab = _make_tab(qapp, settings)
    assert tab._override_targen_row.isHidden()
    assert tab._override_printtarg_row.isHidden()
    assert _targen_enabled(tab)
    assert _printtarg_enabled(tab)


# ---------------------------------------------------------------------------
# ti1 preset: targen greyed, printtarg editable
# ---------------------------------------------------------------------------

def test_knut_preset_locks_targen_only(qapp, settings, monkeypatch):
    tab = _make_tab(qapp, settings)
    monkeypatch.setattr(tab, "_generate_from_ti1", lambda *a, **k: None)
    key = next(iter(KNUT_PRESET_KEYS))
    tab._apply_knut_preset(key, "lock-test")

    assert tab._knut_active
    # targen panel greyed, printtarg stays editable
    assert not _targen_enabled(tab)
    assert _printtarg_enabled(tab)
    # only the targen override row is shown
    assert not tab._override_targen_row.isHidden()
    assert tab._override_printtarg_row.isHidden()
    assert not tab._override_targen_check.isChecked()


def test_knut_targen_override_unlocks(qapp, settings, monkeypatch):
    tab = _make_tab(qapp, settings)
    monkeypatch.setattr(tab, "_generate_from_ti1", lambda *a, **k: None)
    tab._apply_knut_preset(next(iter(KNUT_PRESET_KEYS)), "lock-test")

    tab._override_targen_check.setChecked(True)   # no dialog (programmatic)
    assert _targen_enabled(tab)
    tab._override_targen_check.setChecked(False)
    assert not _targen_enabled(tab)


# ---------------------------------------------------------------------------
# Prebuilt preset: both greyed, two override boxes
# ---------------------------------------------------------------------------

def test_prebuilt_preset_locks_both(qapp, settings, monkeypatch):
    tab = _make_tab(qapp, settings)
    monkeypatch.setattr(tab, "_create_prebuilt_target", lambda *a, **k: None)
    key = next(iter(PREBUILT_PRESETS))
    tab._apply_prebuilt_preset(key, "prebuilt-test")

    assert tab._prebuilt_active
    assert not _targen_enabled(tab)
    assert not _printtarg_enabled(tab)
    assert not tab._override_targen_row.isHidden()
    assert not tab._override_printtarg_row.isHidden()
    # baselines were snapshotted for the Generate-time decision
    assert tab._prebuilt_targen_sig is not None
    assert tab._prebuilt_printtarg_sig is not None


def test_prebuilt_overrides_unlock_independently(qapp, settings, monkeypatch):
    tab = _make_tab(qapp, settings)
    monkeypatch.setattr(tab, "_create_prebuilt_target", lambda *a, **k: None)
    tab._apply_prebuilt_preset(next(iter(PREBUILT_PRESETS)), "prebuilt-test")

    tab._override_printtarg_check.setChecked(True)
    assert _printtarg_enabled(tab)
    assert not _targen_enabled(tab)          # targen still locked

    tab._override_targen_check.setChecked(True)
    assert _targen_enabled(tab)


# ---------------------------------------------------------------------------
# Generate-time routing for a prebuilt preset
# ---------------------------------------------------------------------------

def _route_prebuilt(qapp, settings, monkeypatch, edit=None):
    """Apply a prebuilt preset, optionally edit a panel, return which path ran.

    Returns one of "copy", "relayout", "fresh"."""
    calls: list[str] = []
    tab = _make_tab(qapp, settings)
    monkeypatch.setattr(tab, "_create_prebuilt_target",
                        lambda *a, **k: calls.append("copy"))
    monkeypatch.setattr(tab, "_generate_from_ti1",
                        lambda *a, **k: calls.append("relayout"))
    # The fresh-targen path falls through; abort it cleanly before it runs.
    monkeypatch.setattr(tab, "_handle_target_rename", lambda *a, **k: False)
    tab._apply_prebuilt_preset(next(iter(PREBUILT_PRESETS)), "route-test")
    calls.clear()   # the initial apply copies the bundle; only score the Generate
    if edit == "printtarg":
        tab._override_printtarg_check.setChecked(True)
        tab._set_manual_value("printtarg", "-m", 15)
    elif edit == "targen":
        tab._override_targen_check.setChecked(True)
        tab._set_manual_value("targen", "-f", 333)
    tab._on_generate()
    if not calls:
        return "fresh"
    return calls[-1]


def test_prebuilt_generate_copies_when_untouched(qapp, settings, monkeypatch):
    assert _route_prebuilt(qapp, settings, monkeypatch) == "copy"


def test_prebuilt_generate_relayout_on_printtarg_change(qapp, settings, monkeypatch):
    assert _route_prebuilt(qapp, settings, monkeypatch, edit="printtarg") == "relayout"


def test_prebuilt_generate_fresh_on_targen_change(qapp, settings, monkeypatch):
    assert _route_prebuilt(qapp, settings, monkeypatch, edit="targen") == "fresh"


# ---------------------------------------------------------------------------
# Leaving a preset clears the locks
# ---------------------------------------------------------------------------

def test_leaving_prebuilt_restores_panels(qapp, settings, monkeypatch):
    tab = _make_tab(qapp, settings)
    monkeypatch.setattr(tab, "_create_prebuilt_target", lambda *a, **k: None)
    tab._apply_prebuilt_preset(next(iter(PREBUILT_PRESETS)), "prebuilt-test")
    tab._override_printtarg_check.setChecked(True)

    tab._leave_prebuilt()
    assert not tab._prebuilt_active
    assert _targen_enabled(tab)
    assert _printtarg_enabled(tab)
    assert tab._override_targen_row.isHidden()
    assert tab._override_printtarg_row.isHidden()
    assert not tab._override_printtarg_check.isChecked()


# ---------------------------------------------------------------------------
# Applied editor chart: behaves like a prebuilt preset (both panels greyed),
# but its source is the editor's staging folder rather than a bundled asset.
# ---------------------------------------------------------------------------

applied_argyll = pytest.mark.skipif(not _HAS_ARGYLL, reason="ArgyllCMS not installed")


def _stage_chart(tmp_path, name="applied-test"):
    """A minimal but valid staging folder, as the layout editor's
    _write_chart_into would leave: <name>.ti1/.ti2 + one TIFF page."""
    from workflow import ti2_relayout as R
    src_ti2 = tmp_path / "src.ti2"
    src_ti2.write_text(_TI2)
    spec = R.ChartSpec.from_ti2(src_ti2)
    staging = tmp_path / "staging"
    staging.mkdir()
    res = R.regenerate(spec, R.default_program(spec), staging,
                       _BIN_DIR, basename=name)
    R.save_editor_meta(res.ti2, spec, R.LayoutOptions(), name)
    # _write_chart_into also drops the i1Profiler pair + colour list; stub the
    # i1Profiler file so the carry-over-into-the-run-folder path is exercised.
    (staging / f"{name}-i1profiler.txt").write_text("stub\n")
    return staging, name


@applied_argyll
def test_applied_adopts_ti1_layout_editable(qapp, settings, monkeypatch, tmp_path):
    """Create Chart owns the layout (Knut #93): applying adopts the editor's patch
    set as the .ti1 source — the patch set is fixed (targen greyed) but the layout
    (printtarg) stays editable, and the editor's layout is NOT carried over."""
    tab = _make_tab(qapp, settings)
    monkeypatch.setattr(tab, "_generate_from_ti1", lambda *a, **k: None)
    staging, name = _stage_chart(tmp_path)
    assert tab.apply_external_chart(staging, name) is True

    assert tab._current_mode() == "manual"          # applied lands in manual
    assert not tab._applied_active                   # no longer the locked-import model
    assert tab._preset_ti1_path is not None and tab._preset_ti1_path.is_file()
    assert not _targen_enabled(tab)                  # patch set fixed
    assert _printtarg_enabled(tab)                   # layout editable (owned here)
    assert not tab._override_targen_row.isHidden()
    assert tab._override_printtarg_row.isHidden()


@applied_argyll
def test_applied_regenerates_from_ti1(qapp, settings, tmp_path, monkeypatch):
    """Apply lays the editor's patch set out with the CURRENT layout by
    regenerating from its .ti1 (Knut #93) — not by importing the editor's chart."""
    tab = _make_tab(qapp, settings)
    calls: list[Path] = []
    monkeypatch.setattr(tab, "_generate_from_ti1",
                        lambda p: calls.append(Path(p)))
    staging, name = _stage_chart(tmp_path)
    assert tab.apply_external_chart(staging, name) is True
    assert calls and calls[0].is_file()             # regenerated from the staged .ti1


def _route_applied(qapp, settings, monkeypatch, tmp_path, edit=None):
    calls: list[str] = []
    tab = _make_tab(qapp, settings)
    monkeypatch.setattr(tab, "_import_applied_chart",
                        lambda *a, **k: calls.append("copy"))
    monkeypatch.setattr(tab, "_generate_from_ti1",
                        lambda *a, **k: calls.append("relayout"))
    # apply_external_chart consults the rename guard up front — let it pass so the
    # applied state is established. The fresh-targen branch then falls through to
    # the real generate path; stub the runner call so it scores "fresh" without
    # shelling out.
    monkeypatch.setattr(tab, "_handle_target_rename", lambda *a, **k: True)
    monkeypatch.setattr(tab._creator, "generate",
                        lambda *a, **k: calls.append("fresh"))
    staging, name = _stage_chart(tmp_path)
    tab.apply_external_chart(staging, name)
    calls.clear()
    if edit == "printtarg":
        tab._override_printtarg_check.setChecked(True)
        tab._set_manual_value("printtarg", "-m", 15)
    elif edit == "targen":
        tab._override_targen_check.setChecked(True)
        tab._set_manual_value("targen", "-f", 333)
    tab._on_generate()
    return calls[-1] if calls else "fresh"


@applied_argyll
def test_applied_generate_relayouts_when_untouched(qapp, settings, monkeypatch, tmp_path):
    # The patch set is the .ti1 source now, so an untouched Generate re-lays it out
    # with the current layout (Create Chart owns layout) rather than copying.
    assert _route_applied(qapp, settings, monkeypatch, tmp_path) == "relayout"


@applied_argyll
def test_applied_generate_relayout_on_printtarg_change(qapp, settings, monkeypatch, tmp_path):
    assert _route_applied(qapp, settings, monkeypatch, tmp_path,
                          edit="printtarg") == "relayout"


@applied_argyll
def test_applied_generate_fresh_on_targen_change(qapp, settings, monkeypatch, tmp_path):
    assert _route_applied(qapp, settings, monkeypatch, tmp_path,
                          edit="targen") == "fresh"


@applied_argyll
def test_selecting_default_clears_applied_ti1(qapp, settings, monkeypatch, tmp_path):
    tab = _make_tab(qapp, settings)
    monkeypatch.setattr(tab, "_generate_from_ti1", lambda *a, **k: None)
    staging, name = _stage_chart(tmp_path)
    tab.apply_external_chart(staging, name)
    assert tab._preset_ti1_path is not None

    tab._on_preset_selected(0)        # back to Default → drops the adopted patch set
    assert tab._preset_ti1_path is None
    assert _targen_enabled(tab)
    assert _printtarg_enabled(tab)


# ---------------------------------------------------------------------------
# Reflected chart (loaded in Print/Measure): read-only, both panels greyed,
# nothing copied, generate is a no-op until the user unlocks a panel.
# ---------------------------------------------------------------------------

def _reflect(tab, settings, tmp_path):
    """Write a tiny .ti2 and reflect it (warning suppressed, no TIFFs)."""
    settings.set("reflect_backfill_hide_warning", True)
    ti2 = tmp_path / "loaded.ti2"
    ti2.write_text(_TI2)
    tab.reflect_loaded_chart(ti2, [])
    return ti2


def test_reflect_locks_both(qapp, settings, tmp_path):
    tab = _make_tab(qapp, settings)
    _reflect(tab, settings, tmp_path)
    assert tab._reflected_active
    assert tab._current_mode() == "manual"
    assert not _targen_enabled(tab)
    assert not _printtarg_enabled(tab)
    assert not tab._override_targen_row.isHidden()
    assert not tab._override_printtarg_row.isHidden()


def test_reflect_generate_is_noop_when_untouched(qapp, settings, tmp_path, monkeypatch):
    tab = _make_tab(qapp, settings)
    _reflect(tab, settings, tmp_path)
    calls: list[str] = []
    # The no-op path shows an explanatory InfoDialog — stub it (no event loop).
    monkeypatch.setattr("ui.tabs.tab_chart.InfoDialog",
                        lambda *a, **k: type("D", (), {"exec": lambda self: None})())
    monkeypatch.setattr(tab._creator, "generate", lambda *a, **k: calls.append("gen"))
    tab._on_generate()
    assert calls == []                 # nothing generated
    assert tab._reflected_active       # still just reflecting


def test_reflect_generate_drops_reflection_on_unlock(qapp, settings, tmp_path, monkeypatch):
    tab = _make_tab(qapp, settings)
    _reflect(tab, settings, tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(tab, "_handle_target_rename", lambda *a, **k: True)
    monkeypatch.setattr(tab._creator, "generate", lambda *a, **k: calls.append("gen"))
    tab._override_targen_check.setChecked(True)      # unlock → "build my own"
    tab._set_manual_value("targen", "-f", 100)       # give the fresh build patches
    tab._on_generate()
    assert not tab._reflected_active   # reflection dropped
    assert calls == ["gen"]            # fell through to a real (stubbed) build


def test_selecting_preset_clears_reflection(qapp, settings, tmp_path):
    tab = _make_tab(qapp, settings)
    _reflect(tab, settings, tmp_path)
    assert tab._reflected_active
    tab._leave_reflected()
    assert not tab._reflected_active
    assert _targen_enabled(tab)
    assert _printtarg_enabled(tab)
    assert tab._override_targen_row.isHidden()
    assert tab._override_printtarg_row.isHidden()


# ---------------------------------------------------------------------------
# Vendor preset: editing the patch recipe drops the vendor branding
# ---------------------------------------------------------------------------

def test_override_debrands_vendor_preset(qapp, settings, monkeypatch):
    """A vendor preset (Red River) shows its logo in a clip band. The moment the
    user unlocks "Edit patch recipe" the set is no longer that vendor's certified
    set, so the branding must come off: the clip band reverts to ChromIQ's own
    notes record, with no vendor logo/text left on the chart."""
    from ui.tabs.tab_chart import KNUT_PRESETS_BY_KEY
    from workflow.layout_engine.presets import LayoutRecipe

    tab = _make_tab(qapp, settings)
    panel = getattr(tab, "_manual_layout_panel", None)
    assert panel is not None

    key = "__chromiq_knut_redriver_i1pro_a4_2052p_4pages__"
    tab._knut_active = True
    tab._knut_active_key = key
    panel.set_recipe(LayoutRecipe.from_dict(KNUT_PRESETS_BY_KEY[key].layout_recipe))
    assert tab._current_layout_recipe().clip_content_mode == "image"

    # Don't let the informational modal block the test.
    monkeypatch.setattr("ui.tabs.tab_chart.InfoDialog",
                        lambda *a, **k: type("D", (), {"exec": lambda self: None})())
    assert "Red River" in (tab._active_layout_name() or "")   # branded before
    tab._on_override_clicked("targen", True)

    rec = tab._current_layout_recipe()
    assert rec.clip_content_mode == "notes"   # ChromIQ record, not a vendor logo
    assert not rec.clip_image_path            # no logo image left
    # The "Chart layout <name>" edge stamp must not name the vendor any more.
    name = tab._active_layout_name()
    assert name is None or "Red River" not in name

    # Selecting the preset afresh re-brands it (the drop is not sticky).
    tab._reset_override_checks()
    assert not tab._vendor_debranded
