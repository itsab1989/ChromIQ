"""Settings → Chart Layout tab: preselect to the active combo, and the
save → reopen round-trip.

Regression for #93: the tab always opened on i1/A4, so a preset edited under
any other instrument/paper/mode was saved correctly but invisible on reopen —
which looked like "saving a preset did not work" (Knut)."""
from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.settings import DEFAULTS  # noqa: E402


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


class _FakeSettings:
    def __init__(self, **overrides):
        self._store = {**DEFAULTS, **overrides, "use_chromiq_layout_engine": True}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


def test_chart_layout_tab_preselects_active_combo(_app, tmp_path):
    import core.preset_store as ps
    from ui.dialogs.settings_dialog import SettingsDialog
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        dlg = SettingsDialog(_FakeSettings(), None,
                             layout_combo=("i1", "A4R", "noclip"))
        try:
            assert dlg._layout_instr.currentData() == "i1"
            assert dlg._layout_paper.currentData() == "A4R"
            assert dlg._layout_mode.currentData() == "noclip"
        finally:
            dlg.deleteLater()


def test_chart_layout_preset_saves_and_reopens_visible(_app, tmp_path):
    """Edit a preset under a non-default combo, save, reopen preselected to that
    combo — the edited value must be shown (not the i1/A4 default)."""
    import core.preset_store as ps
    from ui.dialogs.settings_dialog import SettingsDialog
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        combo = ("CM", "A3", "high")
        dlg = SettingsDialog(_FakeSettings(), None, layout_combo=combo)
        try:
            assert dlg._layout_selection() == combo
            # Edit a field on the live panel, then persist via the panel signal.
            dlg._layout_panel.margins["t"].setValue(33.0)
            dlg._on_layout_field_changed()
            dlg._save_and_close()
        finally:
            dlg.deleteLater()

        # Reopen: a fresh dialog, preselected to the same combo, must show 33.
        dlg2 = SettingsDialog(_FakeSettings(), None, layout_combo=combo)
        try:
            assert dlg2._layout_selection() == combo
            assert dlg2._recipe_from_fields().margin_top == 33.0
        finally:
            dlg2.deleteLater()


def test_engine_and_clip_border_mutually_exclusive_on_open(_app, tmp_path):
    """#93: the engine can't share the page with the old printtarg ChromIQ
    clip-border. The engine toggle now lives in Create Chart, so the Settings
    dialog only enforces the rule when it OPENS: with the engine already on, an
    existing both-on config self-heals (clip unchecked + disabled, saved off)."""
    import core.preset_store as ps
    from ui.dialogs.settings_dialog import SettingsDialog
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        # Both persisted on (the stuck state). _FakeSettings forces the engine on.
        dlg = SettingsDialog(_FakeSettings(i1pro_chromiq_clip_style=True),
                             None, layout_combo=("i1", "A4", "noclip"))
        try:
            # Opening with the engine on disables + clears the clip checkbox.
            assert not dlg._chromiq_clip_check.isChecked()
            assert not dlg._chromiq_clip_check.isEnabled()
            # Saving persists the conflict resolved.
            dlg._save_and_close()
            assert dlg._settings.get("use_chromiq_layout_engine") is True
            assert dlg._settings.get("i1pro_chromiq_clip_style") is False
        finally:
            dlg.deleteLater()


def test_chart_layout_clip_enable_for_cm_ss(_app, tmp_path):
    """The CM/SS clip-border On/Off selector is shown only for CM/SS, drives the
    embedded panel's content mode, and persists through save → reopen (#93)."""
    import core.preset_store as ps
    from ui.dialogs.settings_dialog import SettingsDialog
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        combo = ("SS", "A4", "flat")
        dlg = SettingsDialog(_FakeSettings(), None, layout_combo=combo)
        try:
            # hidden for i1, shown for SS (isHidden reflects the explicit
            # setVisible call without needing the tab to be the current one)
            dlg._layout_instr.setCurrentIndex(dlg._layout_instr.findData("i1"))
            assert dlg._layout_clip_enable.isHidden()
            dlg._layout_instr.setCurrentIndex(dlg._layout_instr.findData("SS"))
            assert not dlg._layout_clip_enable.isHidden()
            dlg._layout_paper.setCurrentIndex(dlg._layout_paper.findData("A4"))
            # turn clip on → panel content becomes a band, persist
            dlg._layout_clip_enable.setCurrentIndex(
                dlg._layout_clip_enable.findData("on"))
            assert dlg._layout_panel.clip_enabled()
            assert dlg._recipe_from_fields().clip_content_mode != "off"
            dlg._save_and_close()
        finally:
            dlg.deleteLater()

        dlg2 = SettingsDialog(_FakeSettings(), None, layout_combo=("SS", "A4", "flat"))
        try:
            assert dlg2._layout_clip_enable.currentData() == "on"
            assert dlg2._layout_panel.clip_enabled()
        finally:
            dlg2.deleteLater()


def test_indicator_style_settings_round_trip(_app, tmp_path):
    """The global strip-indicator styling controls (moved out of Create Chart,
    Knut #93) save to the strip_indicator_* / strip_underline_* keys and reload."""
    import core.preset_store as ps
    from ui.dialogs.settings_dialog import SettingsDialog
    from ui.dialogs.layout_options_panel import pt_to_mm
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        st = _FakeSettings()
        dlg = SettingsDialog(st, None)
        try:
            dlg._isty_bold.setChecked(True)
            # The label-size control is now in whole points (#15); it persists
            # as millimetres via pt_to_mm.
            dlg._isty_size.setValue(12)
            dlg._isty_rotation.setCurrentIndex(dlg._isty_rotation.findData(90))
            dlg._isty_align.setCurrentIndex(dlg._isty_align.findData("center"))
            dlg._isty_underline.setCurrentIndex(
                dlg._isty_underline.findData("black"))
            dlg._isty_offset.setValue(2.0)
            dlg._save_and_close()
        finally:
            dlg.deleteLater()
    assert st.get("strip_indicator_bold") is True
    assert st.get("strip_indicator_size_mm") == pytest.approx(pt_to_mm(12))
    assert st.get("strip_indicator_rotation") == 90
    assert st.get("strip_indicator_align") == "center"
    assert st.get("strip_underline_mode") == "black"
    assert st.get("strip_label_offset_mm") == 2.0


def test_layout_info_show_toggle_round_trip(_app, tmp_path):
    """The "Show the Chart layout information panel" toggle defaults to on,
    loads from settings, and persists through save (sibling of the existing
    "Measured from Preview" toggle)."""
    import core.preset_store as ps
    from ui.dialogs.settings_dialog import SettingsDialog
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        st = _FakeSettings()
        dlg = SettingsDialog(st, None)
        try:
            assert dlg._layout_info_show_check.isChecked() is True   # default on
            dlg._layout_info_show_check.setChecked(False)
            dlg._save_and_close()
        finally:
            dlg.deleteLater()
    assert st.get("layout_info_show") is False

    # Reopen with it off → the checkbox reflects the saved state.
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        dlg2 = SettingsDialog(_FakeSettings(layout_info_show=False), None)
        try:
            assert dlg2._layout_info_show_check.isChecked() is False
        finally:
            dlg2.deleteLater()


def test_apply_indicator_style_overlays_recipe():
    """AppSettings.apply_indicator_style overlays the global styling onto a recipe
    (used to seed fresh charts; presets keep their own styling)."""
    from core.settings import AppSettings, INDICATOR_STYLE_KEYS
    from workflow.layout_engine.presets import default_recipe
    s = _FakeSettings(strip_indicator_bold=True, strip_indicator_rotation=270,
                      strip_underline_mode="black")
    # Borrow the real methods on the fake store.
    s.indicator_style = AppSettings.indicator_style.__get__(s)
    s.apply_indicator_style = AppSettings.apply_indicator_style.__get__(s)
    r = s.apply_indicator_style(default_recipe("i1", "A4"))
    assert r.indicator_bold is True
    assert r.indicator_rotation == 270
    assert r.underline_mode == "black"
    assert set(INDICATOR_STYLE_KEYS) <= set(vars(r))


def test_restore_layout_defaults_resets_indicator_style(_app, tmp_path):
    """"Restore factory defaults" on the Chart Layout page also resets the
    strip-indicator style group — a user with an unfortunate label font/size
    had no way back before (#108 follow-up)."""
    import core.preset_store as ps
    from ui.dialogs.settings_dialog import SettingsDialog
    from ui.dialogs.layout_options_panel import mm_to_pt, pt_to_mm
    # Seed a size that lands exactly on the whole-point grid the control now
    # uses (#15), so the loaded value is unambiguous.
    seed_mm = pt_to_mm(9)
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        st = _FakeSettings(**{"strip_indicator_font": "Inter",
                              "strip_indicator_size_mm": seed_mm,
                              "strip_indicator_bold": True})
        dlg = SettingsDialog(st, None)
        try:
            assert dlg._isty_size.value() == 9          # 9 pt, shown in points
            dlg._restore_layout_defaults()
            assert dlg._isty_font.currentData() == DEFAULTS["strip_indicator_font"]
            assert dlg._isty_size.value() == mm_to_pt(
                DEFAULTS["strip_indicator_size_mm"])
            assert dlg._isty_bold.isChecked() is bool(
                DEFAULTS["strip_indicator_bold"])
            dlg._save_and_close()
        finally:
            dlg.deleteLater()
    assert st.get("strip_indicator_font") == DEFAULTS["strip_indicator_font"]
    assert st.get("strip_indicator_size_mm") == DEFAULTS["strip_indicator_size_mm"]


# ---------------------------------------------------------------------------
# Knut's four Chart Layout faults, 4.1.3-beta.13 — driven through the real
# Preferences dialog. See .agent-reports/chartlayout-prefs-challenge.md.
# ---------------------------------------------------------------------------


import json
from pathlib import Path
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# F1 — switching instrument and back must not lose the saved layout
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("combo,other", [
    (("CM", "A3", "high"), "i1"),          # Knut's own case
    (("CM", "A3", "extrahigh"), "i1"),     # the third density
    (("i1", "A4", "noclip"), "CM"),        # clip border OFF — same fault
    (("SS", "A4", "hex"), "CM"),           # hexagonal — same fault
])
def test_switching_instrument_and_back_keeps_the_saved_layout(
        _app, tmp_path, combo, other):
    """Knut, 4.1.3-beta.13: *"If I now change back to Colormunki, then my
    previously saved settings are gone (old defaults pop up)."*

    The store was never wrong — the Mode combo was. Rebuilding it on an
    instrument change dropped the selection onto index 0, so the read key was
    a combination the user had never saved.
    """
    import core.preset_store as ps
    from ui.dialogs.settings_dialog import SettingsDialog
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        dlg = SettingsDialog(_FakeSettings(), None, layout_combo=combo)
        try:
            assert dlg._layout_selection() == combo
            dlg._layout_panel.margins["t"].setValue(12.5)
            assert dlg._layout_store.keys() == ["|".join(combo)]

            dlg._layout_instr.setCurrentIndex(dlg._layout_instr.findData(other))
            dlg._layout_instr.setCurrentIndex(
                dlg._layout_instr.findData(combo[0]))

            assert dlg._layout_selection() == combo, (
                "the tab came back on a different combination, so it read a "
                "key that was never saved and showed shipped defaults")
            assert dlg._layout_panel.margins["t"].value() == 12.5
        finally:
            dlg.deleteLater()


def test_the_store_is_never_the_thing_that_loses_it(_app, tmp_path):
    """The strongest clue in Knut's report: *"If I cancel the preferences
    window and open the preferences Chart Layout tab again, then the settings
    reappear."* Whatever the fix, the store must stay intact throughout —
    a fix that repaired the display by rewriting the store would be worse."""
    import core.preset_store as ps
    from ui.dialogs.settings_dialog import SettingsDialog
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        dlg = SettingsDialog(_FakeSettings(), None,
                             layout_combo=("CM", "A3", "high"))
        try:
            dlg._layout_panel.margins["t"].setValue(12.5)
            for inst in ("i1", "p3", "SS", "CM", "i1", "CM"):
                dlg._layout_instr.setCurrentIndex(
                    dlg._layout_instr.findData(inst))
            assert "CM|A3|high" in dlg._layout_store.keys()
            assert dlg._layout_store.get("CM", "A3", "high").margin_top == 12.5
        finally:
            dlg.deleteLater()


def test_a_paper_the_next_instrument_cannot_offer_comes_back(_app, tmp_path):
    """The SpectroScan has no 594x420. Passing through it must not silently
    downgrade a ColorMunki user from 594x420 to A4 for good."""
    import core.preset_store as ps
    from ui.dialogs.settings_dialog import SettingsDialog
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        dlg = SettingsDialog(_FakeSettings(), None,
                             layout_combo=("CM", "594x420", "freehand"))
        try:
            assert dlg._layout_paper.currentData() == "594x420"
            dlg._layout_instr.setCurrentIndex(dlg._layout_instr.findData("SS"))
            assert dlg._layout_paper.currentData() != "594x420"   # not offered
            dlg._layout_instr.setCurrentIndex(dlg._layout_instr.findData("CM"))
            assert dlg._layout_paper.currentData() == "594x420"
        finally:
            dlg.deleteLater()


def test_a_paper_the_next_instrument_does_offer_is_carried_across(
        _app, tmp_path):
    """The other half: an A3 user who switches instrument stays on A3 the
    first time (there is nothing remembered for the new instrument yet)."""
    import core.preset_store as ps
    from ui.dialogs.settings_dialog import SettingsDialog
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        dlg = SettingsDialog(_FakeSettings(), None,
                             layout_combo=("CM", "A3", "high"))
        try:
            dlg._layout_instr.setCurrentIndex(dlg._layout_instr.findData("i1"))
            assert dlg._layout_paper.currentData() == "A3"
        finally:
            dlg.deleteLater()


# ---------------------------------------------------------------------------
# F1b — the user must be able to tell "saved" from "ChromIQ's default"
# ---------------------------------------------------------------------------

def test_the_tab_says_whether_this_combination_is_saved(_app, tmp_path):
    """A combination that was never saved has to read as "nothing saved yet",
    not as "my settings vanished"."""
    import core.preset_store as ps
    from ui.dialogs.settings_dialog import SettingsDialog
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        dlg = SettingsDialog(_FakeSettings(), None,
                             layout_combo=("CM", "A3", "high"))
        try:
            hint = dlg._layout_saved_hint
            assert "Nothing saved" in hint.text()
            dlg._layout_panel.margins["t"].setValue(12.5)
            assert "saved" in hint.text() and "Nothing saved" not in hint.text()
            dlg._layout_mode.setCurrentIndex(
                dlg._layout_mode.findData("extrahigh"))
            assert "Nothing saved" in hint.text()
        finally:
            dlg.deleteLater()


# ---------------------------------------------------------------------------
# F2 — the tab must say it opens on the current chart's combination
# ---------------------------------------------------------------------------

def test_the_tab_explains_that_it_opens_on_the_current_charts_combination(
        _app, tmp_path):
    """Knut: *"the preferences ==> Chart Layout tab does not specify that the
    currently loaded chart's settings for the instrument and paper combination
    is automatically loaded in the tab."*"""
    from PyQt6.QtWidgets import QLabel
    import core.preset_store as ps
    from ui.dialogs.settings_dialog import SettingsDialog
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        dlg = SettingsDialog(_FakeSettings(), None,
                             layout_combo=("CM", "A3", "high"))
        try:
            text = " ".join(w.text() for w in dlg.findChildren(QLabel))
            assert "opens on" in text
            for word in ("Instrument", "Paper", "Mode", "current chart"):
                assert word in text, word
        finally:
            dlg.deleteLater()


# ---------------------------------------------------------------------------
# F3 — Density is shown wherever it changes the layout (both hosts)
# ---------------------------------------------------------------------------
# → tests/test_layout_options_panel.py
# REPLACES test_colormunki_density_hidden_in_area_first, which asserts the
# behaviour this change removes. That test is green today and guards the bug.

def test_density_really_does_change_an_area_first_layout():
    """The measurement the two tests above rest on — so a future refactor
    that makes Density genuinely moot fails HERE first, not in the UI."""
    from workflow.layout_engine import geometry, instruments, papers
    from workflow.layout_engine.presets import default_recipe
    w, h = papers.dimensions_mm("A3")

    def cap(mode, **kw):
        r = default_recipe("CM", "A3", mode=mode)
        r.margin_top = r.margin_right = r.margin_bottom = r.margin_left = 6.0
        r.border, r.patch_area_align = 6.0, "top-left"
        r.layout_mode = "area_first"
        for k, v in kw.items():
            setattr(r, k, v)
        g = instruments.geom_from_build_kwargs(r.build_kwargs())
        return geometry.patches_per_sheet(g, w, h)

    auto = [cap(m, area_method="by_grid", area_cols=0, area_rows=0)
            for m in ("freehand", "high", "extrahigh")]
    assert len(set(auto)) == 3, f"density is moot in area-first? {auto}"

    pinned = [cap(m, area_method="by_grid", area_cols=20, area_rows=30)
              for m in ("freehand", "high", "extrahigh")]
    assert len(set(pinned)) == 1, f"a pinned grid should ignore it: {pinned}"


# ---------------------------------------------------------------------------
# F4 — the export/import contract
# ---------------------------------------------------------------------------

def test_the_exported_key_matches_the_recipe_body(_app, tmp_path):
    """Knut suspects the exported key. It is not wrong — but it must be
    provably consistent with the body, because import re-derives it."""
    import core.preset_store as ps
    from workflow.layout_engine.presets import LayoutRecipe
    from ui.dialogs.settings_dialog import SettingsDialog
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        dlg = SettingsDialog(_FakeSettings(), None,
                             layout_combo=("CM", "A3", "high"))
        try:
            dlg._layout_panel.margins["t"].setValue(12.5)
            for inst, mode in (("i1", "noclip"), ("SS", "hex")):
                dlg._layout_instr.setCurrentIndex(
                    dlg._layout_instr.findData(inst))
                dlg._layout_mode.setCurrentIndex(
                    dlg._layout_mode.findData(mode))
                dlg._layout_panel.margins["t"].setValue(7.5)
            blob = dlg._layout_store.as_named_dict()
            assert blob
            for key, rec in blob.items():
                assert LayoutRecipe.from_dict(rec).preset_key() == key
        finally:
            dlg.deleteLater()


def test_importing_an_unrelated_json_does_not_overwrite_real_presets(
        _app, tmp_path):
    """LayoutRecipe.from_dict drops every field it does not know, so any
    ``{str: dict}`` JSON used to import as a pile of DEFAULT recipes and
    silently replace the user's own under their default keys."""
    import core.preset_store as ps
    import ui.widgets as W
    from ui.dialogs.settings_dialog import SettingsDialog
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        dlg = SettingsDialog(_FakeSettings(), None,
                             layout_combo=("i1", "A4", "clip"))
        try:
            dlg._layout_panel.margins["t"].setValue(13.0)
            junk = tmp_path / "not-a-preset.json"
            junk.write_text(json.dumps({"a": {"hello": "world"}, "b": {"x": 1}}), encoding="utf-8")
            with mock.patch.object(W, "open_file_dialog",
                                   lambda *a, **k: str(junk)):
                dlg._import_layout_presets()
            assert dlg._layout_store.get("i1", "A4", "clip").margin_top == 13.0
        finally:
            dlg.deleteLater()


def test_import_still_accepts_a_real_export(_app, tmp_path):
    """The guard above must not break the round-trip it protects."""
    import core.preset_store as ps
    import ui.widgets as W
    from ui.dialogs.settings_dialog import SettingsDialog
    from workflow.layout_engine.presets import default_recipe
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        r = default_recipe("CM", "A3", mode="extrahigh")
        r.margin_top = 9.25
        blob = tmp_path / "export.json"
        blob.write_text(json.dumps({r.preset_key(): r.to_dict()}), encoding="utf-8")
        dlg = SettingsDialog(_FakeSettings(), None,
                             layout_combo=("CM", "A3", "extrahigh"))
        try:
            with mock.patch.object(W, "open_file_dialog",
                                   lambda *a, **k: str(blob)):
                dlg._import_layout_presets()
            assert dlg._layout_store.get(
                "CM", "A3", "extrahigh").margin_top == 9.25
        finally:
            dlg.deleteLater()


def test_a_preset_for_a_dropped_instrument_survives_a_save(_app, tmp_path):
    """DTP41/DTP51 are gone from the picker but may still sit in a user's
    presets folder. An unrelated edit + OK must not delete them."""
    import core.preset_store as ps
    from ui.dialogs.settings_dialog import SettingsDialog
    from workflow.layout_engine.presets import default_recipe
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        d = Path(tmp_path) / "Chart Layout"
        d.mkdir(parents=True, exist_ok=True)
        r = default_recipe("41", "A4", mode="default")
        r.margin_top = 7.7
        (d / "41_A4_default.json").write_text(json.dumps({
            "chromiq_preset_version": 1, "tab": "chart_layout",
            "name": "41|A4|default", "data": r.to_dict()}), encoding="utf-8")
        dlg = SettingsDialog(_FakeSettings(), None,
                             layout_combo=("i1", "A4", "clip"))
        dlg._layout_panel.margins["t"].setValue(5.5)
        dlg._save_and_close()
        names = sorted(json.loads(p.read_text(encoding="utf-8"))["name"]
                       for p in d.glob("*.json"))
        assert "41|A4|default" in names
