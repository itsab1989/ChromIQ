""""Darkest black" is a Build Profile option, not a preference (Basti,
2026-11-12).

It was placed in Preferences > Beta as one global setting in 4.3.31. Basti:
it "should have been in build profile tab manual module", and it must be
"savable as default and as part of a preset", exactly like its neighbour
"Keep the original hue". So:

1. The row ("Darkest black:", Neutral (recommended) / Deepest, with its
   tooltip) stands among the engine-only Manual rows, directly under "Keep
   the original hue", built like the other choice rows there. It is shown
   only while the profile engine switch is on, reaches a build only then,
   and the colprof comparison build never gets it.
2. Per target, saved as a default and into presets like the hue option
   (only while the engine is on; a preset without the value loads Neutral);
   Restore defaults covers it (factory: Neutral).
3. Preferences > Beta no longer holds it. Settings schema 33 migrates the old
   global value: Deepest becomes the saved Build Profile default AND what a
   target stored before this version reads; Neutral or nothing changes
   nothing; the old key is removed.
4. Guided mode has no engine rows and builds every one of them with its
   factory value, so "Darkest black" is Neutral in a Guided build.
6. The build record (meta.json ``profile_build``) names the black used, and
   nothing reads the removed preference any more.

The spec block is per_target_settings.md, "Darkest black" (awaiting
confirmation).
"""
from __future__ import annotations

import dataclasses
import re
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QSettings  # noqa: E402

from core.settings import DEFAULTS, SETTINGS_SCHEMA, AppSettings  # noqa: E402
from workflow import engine_builder as eb  # noqa: E402
from workflow.profile_builder import ProfileParams  # noqa: E402

from tests.test_the_new_profile_engine_is_one_switch import (  # noqa: E402
    _Fake, _built_settings, _quiet_windows, _run_with_ti3, _tab)

ROOT = Path(__file__).resolve().parent.parent


def _store(tmp_path, schema=32, **stored) -> AppSettings:
    """A settings store as an older ChromIQ left it on disk."""
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "old.ini"), QSettings.Format.IniFormat)
    s._qs.setValue("settings_schema", schema)
    for k, v in stored.items():
        s._qs.setValue(k, v)
    return s


def _pick(tab, value):
    tab._m_black_combo.setCurrentIndex(tab._m_black_combo.findData(value))


# ---------------------------------------------------------------------------
# 1. the row
# ---------------------------------------------------------------------------

def test_the_row_stands_under_keep_the_original_hue_among_the_engine_rows(
        tmp_path, qtbot):
    from PyQt6.QtWidgets import QLabel

    from ui.widgets import NoScrollComboBox
    tab = _tab(tmp_path)
    qtbot.addWidget(tab)
    rows = tab._m_engine_rows_widget
    combo = tab._m_black_combo
    assert rows.isAncestorOf(combo) and rows.isAncestorOf(tab._m_black_tip)
    col = rows.layout()
    layouts = [col.itemAt(i).layout() for i in range(col.count())]
    hue = next(i for i, lay in enumerate(layouts)
               if lay.itemAt(0).widget() is tab._m_hue_cb)
    black = layouts[hue + 1]               # directly under the hue row
    label = black.itemAt(0).widget()
    assert isinstance(label, QLabel) and label.text() == "Darkest black:"
    assert black.itemAt(1).widget() is combo
    assert black.itemAt(2).widget() is tab._m_black_tip
    # built like its neighbouring choice rows (Out-of-gamut rendering)
    assert type(combo) is type(tab._m_render_combo) is NoScrollComboBox
    assert combo.objectName() == tab._m_render_combo.objectName() \
        == "compact_input"
    render = next(lay for lay in layouts
                  if lay.itemAt(1).widget() is tab._m_render_combo)
    assert black.stretch(1) == render.stretch(1) == 1
    # one label column: the form aligner gave both labels the same width
    assert label.minimumWidth() == render.itemAt(0).widget().minimumWidth()
    assert label.minimumWidth() > 0
    assert [combo.itemData(i) for i in range(combo.count())] == [
        "neutral", "deepest"]
    assert [combo.itemText(i) for i in range(combo.count())] == [
        "Neutral (recommended)", "Deepest"]
    assert combo.currentData() == "neutral"            # factory


def test_the_row_is_shown_only_with_the_engine_on(tmp_path, qtbot):
    tab = _tab(tmp_path)                                # engine off
    qtbot.addWidget(tab)
    assert tab._m_engine_rows_widget.isHidden()
    tab._settings.set("profile_engine_beta", True)
    tab._refresh_engine_rows()
    assert not tab._m_engine_rows_widget.isHidden()
    assert not tab._m_black_combo.isHidden()
    tab._settings.set("profile_engine_beta", False)
    tab._refresh_engine_rows()
    assert tab._m_engine_rows_widget.isHidden()


def test_the_choice_reaches_a_build_only_with_the_engine_on(tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    assert tab._collect_manual_profile().black_depth == "neutral"
    _pick(tab, "deepest")
    assert tab._collect_manual_profile().black_depth == "deepest"
    tab._settings.set("profile_engine_beta", False)
    assert tab._collect_manual_profile().black_depth == "neutral"
    assert ProfileParams(ti3_path=Path("x.ti3")).black_depth == "neutral"


def test_the_engine_takes_it_from_the_build_not_from_the_preferences(
        monkeypatch, tmp_path):
    s = _built_settings(monkeypatch, tmp_path,
                        _Fake(profile_engine_beta=True),
                        black_depth="deepest")
    assert s.black_depth == "deepest"
    from workflow.profile_engine.builder import effective_engine_candidates
    assert "a88-black-deepest" in effective_engine_candidates(s)
    # an old global value left on disk reaches nothing
    s = _built_settings(monkeypatch, tmp_path, _Fake(
        profile_engine_beta=True, profile_engine_black_depth="deepest"))
    assert s.black_depth == "neutral"
    # an unknown value in a build reads as Neutral, never an error
    assert eb.settings_from_params(ProfileParams(
        ti3_path=Path("x.ti3"), black_depth="balanced")).black_depth \
        == "neutral"


def _engine_done(tmp_path, qtbot, monkeypatch):
    from ui.tabs import tab_profile as tp
    tab = _tab(tmp_path, profile_engine_beta=True,
               profile_engine_colprof_comparison=True)
    qtbot.addWidget(tab)
    run, ti3 = _run_with_ti3(tab, tmp_path)
    _quiet_windows(monkeypatch, tab)
    icc = ti3.with_suffix(".icc")
    tab._active_params = ProfileParams(ti3_path=ti3, black_depth="deepest")
    tab._engine_builder.reference_failed = ""
    tab._engine_builder.last_record = {"builder": "engine",
                                       "black_depth": "deepest"}
    monkeypatch.setattr(tab._runner, "tool_is_installed", lambda _t: True)
    started: list = []
    monkeypatch.setattr(tp.ProfileBuilder, "build",
                        lambda self, p, on_line, on_finish: started.append(p))
    return tab, run, icc, started


def test_the_comparison_profile_is_built_without_it(tmp_path, qtbot,
                                                    monkeypatch):
    tab, run, icc, started = _engine_done(tmp_path, qtbot, monkeypatch)
    icc.write_bytes(b"the engine made this " * 100)
    tab._on_engine_done(0)
    assert started and started[0].black_depth == "neutral"


# ---------------------------------------------------------------------------
# 2. per target, saved default, preset, restore defaults
# ---------------------------------------------------------------------------

def test_a_preset_carries_it_only_when_saved_with_the_engine_on(tmp_path,
                                                                 qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    _pick(tab, "deepest")
    on = tab._m_collect_preset_data()
    assert on["black_depth"] == "deepest"
    _pick(tab, "neutral")
    assert tab._m_collect_preset_data()["black_depth"] == "neutral"
    tab._m_apply_preset_data(on)
    assert tab._m_black_combo.currentData() == "deepest"
    tab._settings.set("profile_engine_beta", False)
    off = tab._m_collect_preset_data()
    assert "black_depth" not in off                    # nobody could see it
    tab._settings.set("profile_engine_beta", True)
    tab._m_apply_preset_data(off)
    assert tab._m_black_combo.currentData() == "neutral"
    # a preset from before the move, and one with a value this build does
    # not know, load as Neutral
    for old in ({"quality": "m"}, {"black_depth": "balanced"}):
        _pick(tab, "deepest")
        tab._m_apply_preset_data(old)
        assert tab._m_black_combo.currentData() == "neutral", old


def test_presets_round_trip_through_the_preset_list(tmp_path, qtbot,
                                                    monkeypatch):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    store: dict = {}
    monkeypatch.setattr(tab, "_m_load_presets", lambda: dict(store))
    _pick(tab, "deepest")
    store["deep"] = tab._m_collect_preset_data()
    tab._settings.set("profile_engine_beta", False)
    store["engine off"] = tab._m_collect_preset_data()
    tab._settings.set("profile_engine_beta", True)
    tab._m_populate_preset_combo(store)
    combo = tab._m_preset_combo
    _pick(tab, "neutral")
    combo.setCurrentIndex(combo.findData("deep"))
    tab._on_m_preset_selected(combo.currentIndex())
    assert tab._m_black_combo.currentData() == "deepest"
    combo.setCurrentIndex(combo.findData("engine off"))
    tab._on_m_preset_selected(combo.currentIndex())
    assert tab._m_black_combo.currentData() == "neutral"


def test_save_as_default_takes_it_only_with_the_engine_on(tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    tab._stack.setCurrentIndex(1)                       # Manual
    assert tab._settings.get("manual2_colprof_black_depth") is None
    _pick(tab, "deepest")
    tab._on_save_defaults()
    assert tab._settings.get("manual2_colprof_black_depth") == "deepest"
    _pick(tab, "neutral")
    tab._on_m_preset_selected(0)                        # "Default settings"
    assert tab._m_black_combo.currentData() == "deepest"
    tab._settings.set("profile_engine_beta", False)
    _pick(tab, "neutral")
    tab._on_save_defaults()
    assert tab._settings.get("manual2_colprof_black_depth") == "deepest"
    # Guided's Save as default never writes it (Guided has no such row)
    tab._settings.set("profile_engine_beta", True)
    tab._stack.setCurrentIndex(0)
    _pick(tab, "neutral")
    tab._on_save_defaults()
    assert tab._settings.get("manual2_colprof_black_depth") == "deepest"


def test_restore_defaults_covers_it(tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    _pick(tab, "deepest")
    tab._restore_defaults()
    assert tab._m_black_combo.currentData() == "neutral"   # factory
    tab._settings.set("manual2_colprof_black_depth", "deepest")
    tab._restore_defaults()
    assert tab._m_black_combo.currentData() == "deepest"
    tab._settings.set("manual2_colprof_black_depth", "nonsense")
    tab._restore_defaults()
    assert tab._m_black_combo.currentData() == "neutral"


def test_each_target_keeps_its_own_with_the_engine_on_and_off(tmp_path,
                                                              qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    run, _ti3 = _run_with_ti3(tab, tmp_path)
    _pick(tab, "deepest")
    assert tab.save_target_settings(store=run) is True
    assert run.load_meta().profile_settings["black_depth"] == "deepest"
    other, _ = _run_with_ti3(tab, tmp_path, name="Other")
    _pick(tab, "neutral")
    tab.save_target_settings(store=other)
    assert other.load_meta().profile_settings["black_depth"] == "neutral"
    tab._m_apply_preset_data(run.load_meta().profile_settings)
    assert tab._m_black_combo.currentData() == "deepest"
    tab._m_apply_preset_data(other.load_meta().profile_settings)
    assert tab._m_black_combo.currentData() == "neutral"
    # the engine off: a write keeps the target's choice
    tab._m_apply_preset_data(run.load_meta().profile_settings)
    tab._settings.set("profile_engine_beta", False)
    tab._profile_written_cache().clear()
    tab.save_target_settings(store=run)
    assert run.load_meta().profile_settings["black_depth"] == "deepest"


def _load_target(tab, run, monkeypatch):
    import workflow.per_target_settings as pts
    monkeypatch.setattr(pts, "store_for_target", lambda _ctl: run)
    return tab.load_target_settings()


def test_a_target_stored_before_the_move_reads_the_old_global_value(
        tmp_path, qtbot, monkeypatch):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    run, _ti3 = _run_with_ti3(tab, tmp_path)
    tab.save_target_settings(store=run)
    meta = run.load_meta()
    meta.profile_settings = {k: v for k, v in meta.profile_settings.items()
                             if k != "black_depth"}
    run.save_meta(meta)
    # nobody had Deepest: Neutral
    _pick(tab, "deepest")
    assert _load_target(tab, run, monkeypatch) is True
    assert tab._m_black_combo.currentData() == "neutral"
    # the migration recorded a global Deepest: the old target reads it
    tab._settings.set("manual2_colprof_black_depth_older_targets", "deepest")
    _pick(tab, "neutral")
    assert _load_target(tab, run, monkeypatch) is True
    assert tab._m_black_combo.currentData() == "deepest"
    # ...until it is changed there: then the target's own value counts
    _pick(tab, "neutral")
    tab._profile_written_cache().clear()
    tab.save_target_settings(store=run)
    _pick(tab, "deepest")
    _load_target(tab, run, monkeypatch)
    assert tab._m_black_combo.currentData() == "neutral"


def test_a_target_with_nothing_stored_opens_on_the_saved_default(
        tmp_path, qtbot, monkeypatch):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    run, _ti3 = _run_with_ti3(tab, tmp_path)
    meta = run.load_meta()
    meta.profile_settings = {}
    run.save_meta(meta)
    _pick(tab, "deepest")
    assert _load_target(tab, run, monkeypatch) is False
    assert tab._m_black_combo.currentData() == "neutral"   # S4 to S7
    tab._settings.set("manual2_colprof_black_depth", "deepest")
    _pick(tab, "neutral")
    _load_target(tab, run, monkeypatch)
    assert tab._m_black_combo.currentData() == "deepest"


# ---------------------------------------------------------------------------
# 3. Preferences no longer holds it; the migration
# ---------------------------------------------------------------------------

def test_preferences_has_no_black_option_and_writes_no_black_key(qtbot):
    from ui.dialogs.settings_dialog import SettingsDialog
    fake = _Fake(DEFAULTS)
    dlg = SettingsDialog(fake)
    qtbot.addWidget(dlg)
    assert not hasattr(dlg, "_black_depth_combo")
    # the switch and the comparison option stay
    assert dlg._profile_engine_check is not None
    assert dlg._colprof_comparison_check is not None
    lay = dlg._beta_page.layout()
    texts = []
    for i in range(lay.count()):
        w = lay.itemAt(i).widget()
        if w is not None:
            from PyQt6.QtWidgets import QLabel
            texts += [lab.text() for lab in w.findChildren(QLabel)]
    assert "Darkest black:" not in texts
    dlg._profile_engine_check.setChecked(True)
    dlg._save_and_close()
    assert "profile_engine_black_depth" not in fake
    assert "profile_engine_black_depth" not in DEFAULTS


def test_the_schema_is_bumped_for_the_move():
    assert SETTINGS_SCHEMA >= 33


@pytest.mark.parametrize("engine_on", [True, False])
@pytest.mark.parametrize("raw", ["deepest", "Deepest", " DEEPEST "])
def test_a_global_deepest_is_carried_into_build_profile(tmp_path, engine_on,
                                                        raw):
    """Whatever the switch says: the old value was kept with the engine off
    and applied the day it went on, so it is carried either way."""
    s = _store(tmp_path, profile_engine_beta=engine_on,
               profile_engine_black_depth=raw)
    dropped = s.migrate()
    assert any(k.startswith("profile_engine_black_depth") for k in dropped)
    assert s._qs.value("profile_engine_black_depth", None) is None
    assert s.get("manual2_colprof_black_depth") == "deepest"
    assert s.get("manual2_colprof_black_depth_older_targets") == "deepest"
    assert int(s._qs.value("settings_schema")) == SETTINGS_SCHEMA


@pytest.mark.parametrize("engine_on", [True, False])
@pytest.mark.parametrize("raw", ["neutral", "Neutral", "balanced", ""])
def test_a_global_neutral_or_unknown_changes_nothing_but_the_old_key(
        tmp_path, engine_on, raw):
    s = _store(tmp_path, profile_engine_beta=engine_on,
               profile_engine_black_depth=raw)
    s.migrate()
    assert s._qs.value("profile_engine_black_depth", None) is None
    assert s._qs.value("manual2_colprof_black_depth", None) is None
    assert s._qs.value("manual2_colprof_black_depth_older_targets",
                       None) is None


def test_no_stored_value_writes_nothing(tmp_path):
    s = _store(tmp_path, profile_engine_beta=True)
    dropped = s.migrate()
    assert not any("black_depth" in k for k in dropped)
    assert s._qs.value("manual2_colprof_black_depth", None) is None
    assert s._qs.value("manual2_colprof_black_depth_older_targets",
                       None) is None


def test_a_saved_default_already_there_is_not_overwritten(tmp_path):
    s = _store(tmp_path, profile_engine_black_depth="deepest",
               manual2_colprof_black_depth="neutral")
    s.migrate()
    assert s.get("manual2_colprof_black_depth") == "neutral"
    assert s.get("manual2_colprof_black_depth_older_targets") == "deepest"


def test_the_migration_runs_once(tmp_path):
    s = _store(tmp_path, schema=SETTINGS_SCHEMA,
               profile_engine_black_depth="deepest")
    assert s.migrate() == []
    # a store already at this schema is left exactly as it is
    assert s._qs.value("profile_engine_black_depth") == "deepest"


def _migrated_tab(tmp_path, qtbot, raw):
    """The tab over a store an older ChromIQ left, migrated as main() does."""
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_profile import TabProfile
    s = _store(tmp_path, profile_engine_beta=True,
               **({} if raw is None else {"profile_engine_black_depth": raw}))
    s.migrate()
    tab = TabProfile(ArgyllRunner(s), s)
    qtbot.addWidget(tab)
    return tab


@pytest.mark.parametrize("raw,want", [("deepest", "deepest"),
                                      ("neutral", "neutral"),
                                      (None, "neutral")])
def test_after_the_migration_new_and_old_targets_and_presets(
        tmp_path, qtbot, monkeypatch, raw, want):
    tab = _migrated_tab(tmp_path, qtbot, raw)
    # the tab opens on the saved default
    tab._restore_defaults()
    assert tab._m_black_combo.currentData() == want
    # a NEW target (nothing stored) starts with it
    new, _ = _run_with_ti3(tab, tmp_path, name="New")
    meta = new.load_meta()
    meta.profile_settings = {}
    new.save_meta(meta)
    _pick(tab, "neutral" if want == "deepest" else "deepest")
    _load_target(tab, new, monkeypatch)
    assert tab._m_black_combo.currentData() == want
    # an EXISTING target, stored before the move (no "black_depth")
    old, _ = _run_with_ti3(tab, tmp_path, name="Old")
    tab.save_target_settings(store=old)
    meta = old.load_meta()
    meta.profile_settings = {k: v for k, v in meta.profile_settings.items()
                             if k != "black_depth"}
    old.save_meta(meta)
    _pick(tab, "neutral" if want == "deepest" else "deepest")
    _load_target(tab, old, monkeypatch)
    assert tab._m_black_combo.currentData() == want
    # a PRESET from before never held the value: Neutral (as a preset saved
    # with the engine off), whatever the global value was
    _pick(tab, "deepest")
    tab._m_apply_preset_data({"quality": "m", "hue_rendering": "argyll"})
    assert tab._m_black_combo.currentData() == "neutral"
    # and the build takes what the tab shows
    tab._m_apply_preset_data({"black_depth": want})
    assert tab._collect_manual_profile().black_depth == want


# ---------------------------------------------------------------------------
# 4. Guided builds
# ---------------------------------------------------------------------------

def test_a_guided_build_uses_neutral_like_every_other_engine_row(
        tmp_path, qtbot, monkeypatch):
    """Guided has no engine rows; today it builds each of them with its
    factory value whatever Manual or the target says (spectral off, v2,
    noise off, Argyll-matched, hue not kept). "Darkest black" does the
    same."""
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    run, _ti3 = _run_with_ti3(tab, tmp_path)
    tab._m_spectral_cb.setChecked(True)
    tab._m_noise_cb.setChecked(True)
    tab._m_hue_cb.setChecked(True)
    tab._m_render_combo.setCurrentIndex(
        tab._m_render_combo.findData("bijective"))
    _pick(tab, "deepest")
    tab.save_target_settings(store=run)
    tab._settings.set("manual2_colprof_black_depth", "deepest")
    tab._stack.setCurrentIndex(0)                       # Guided
    g = tab._collect_guided_profile()
    assert (g.spectral_physics, g.icc_version, g.noise_model,
            g.render_style, g.hue_rendering) == (
                False, "2", False, "argyll", "argyll")
    assert g.black_depth == "neutral"
    assert eb.settings_from_params(g).black_depth == "neutral"


def test_the_tooltip_says_what_a_guided_build_uses():
    src = (ROOT / "ui/tabs/tab_profile.py").read_text("utf-8")
    i = src.index('tr("Darkest black"),')
    tip = src[i:src.index("min_width=680", i)]
    flat = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', tip))
    assert ("This choice is used for builds in Manual mode. Guided mode "
            "always builds with Neutral.") in flat
    assert "Preferences" not in flat and "—" not in flat


# ---------------------------------------------------------------------------
# 6. the record, and nothing reads the old preference
# ---------------------------------------------------------------------------

def test_the_build_record_names_the_black_the_tab_chose(monkeypatch,
                                                        tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    run, _ti3 = _run_with_ti3(tab, tmp_path)
    tab._stack.setCurrentIndex(1)
    _pick(tab, "deepest")
    params = tab._collect_manual_profile()
    s = _built_settings(monkeypatch, tmp_path,
                        _Fake(profile_engine_beta=True),
                        black_depth=params.black_depth)
    rec = eb.EngineLines(lambda _l: None).record(s)
    assert rec["black_depth"] == "deepest"
    assert "black_depth='deepest'" in rec["settings"]
    rec = eb.EngineLines(lambda _l: None).record(
        eb.settings_from_params(dataclasses.replace(params,
                                                    black_depth="neutral")))
    assert rec["black_depth"] == "neutral"


def test_nothing_reads_the_removed_preference():
    out = subprocess.run(
        ["git", "grep", "-n", "profile_engine_black_depth", "--",
         "*.py", ":!tests/*", ":!benchmarks/*"],
        cwd=ROOT, capture_output=True, text=True, check=False).stdout
    hits = [ln for ln in out.splitlines() if ln.strip()]
    assert hits, "git grep found nothing at all: not a git checkout?"
    assert all(ln.startswith("core/settings.py:") for ln in hits), hits
    assert not hasattr(eb, "black_depth_setting")


def test_the_spec_records_the_move_as_awaiting_confirmation():
    spec = (ROOT / "docs/design/per_target_settings.md").read_text("utf-8")
    i = spec.index("Darkest black (Build Profile, Manual)")
    block = spec[spec.rindex("### ", 0, i):]
    block = block[:block.index("\n### ", 1)]
    assert "Awaiting confirmation" in block.splitlines()[0]
    assert "**Confirmed by:** *nobody yet.*" in block
    for word in ("manual2_colprof_black_depth", "black_depth",
                 "manual2_colprof_black_depth_older_targets", "schema 33",
                 "Guided"):
        assert word in block, word


# ---------------------------------------------------------------------------
# byte identity: the tab's choice builds what the old preference built
# (heavy engine tier: tests/_engine_tier.py HEAVY_TESTS)
# ---------------------------------------------------------------------------

def _argyll() -> "str | None":
    from tests.argyll_env import argyll_bin_dir
    d = argyll_bin_dir()
    return str(d) if d is not None else None


@pytest.mark.slow
@pytest.mark.skipif(_argyll() is None, reason="ArgyllCMS not installed")
def test_the_tabs_choice_builds_the_same_bytes_as_the_old_preference(
        tmp_path, qtbot):
    """Until 2026-11-12 an engine build took ``settings_from_params(params)``
    and then set ``black_depth`` from the global preference. Now the value
    comes with the tab's ProfileParams. For Neutral (the default) and for
    Deepest, the profile is byte for byte the one the old path built."""
    from datetime import datetime

    from workflow.profile_engine import builder as B
    from workflow.profile_engine import gamut_map
    tab = _tab(tmp_path, profile_engine_beta=True)
    qtbot.addWidget(tab)
    _run, ti3 = _run_with_ti3(tab, tmp_path)
    tab._stack.setCurrentIndex(1)
    when = datetime(2026, 1, 1)

    def build(settings, name):
        settings.argyll_bin = _argyll()
        settings.gammap_mode = eb.ENGINE_MODE
        settings.engine_workers = 0
        settings.timestamp = when
        (tmp_path / name).mkdir()
        out = tmp_path / name / "p.icc"
        gamut_map._ORACLE_CACHE.clear()
        B.build_profile(ti3, out, settings)
        return out.read_bytes()

    for black in ("neutral", "deepest"):
        _pick(tab, black)
        params = tab._collect_manual_profile()
        assert params.black_depth == black
        new = build(eb.settings_from_params(params), f"new-{black}")
        old_settings = eb.settings_from_params(
            dataclasses.replace(params, black_depth="neutral"))
        old_settings.black_depth = black        # what the preference did
        old = build(old_settings, f"old-{black}")
        assert new == old, black
