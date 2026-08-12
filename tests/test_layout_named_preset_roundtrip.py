"""A named Create-Chart preset carries the ChromIQ layout-engine recipe (#93).

Engine options set in the Manual module must save into / restore from the named
presets just like the printtarg options do, so the saved layout isn't lost.
"""
import tempfile
from dataclasses import replace

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_chart import TabChart  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(qapp):
    s = AppSettings()
    s._qs = QSettings(tempfile.mktemp(suffix=".ini"), QSettings.Format.IniFormat)
    # These tests exercise the printtarg path explicitly — since 4.0.0
    # the ChromIQ layout engine is the Manual default (schema 18), so
    # the mode under test is pinned rather than inherited.
    s.set("use_chromiq_layout_engine", False)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    return t


def test_named_preset_restores_engine_recipe(qapp):
    t = _tab(qapp)
    rec = LayoutRecipe(
        instrument="i1", paper="A4", clip_border=True, pscale=0.9,
        indicator_font="Inter", indicator_bold=True, underline_mode="cycle",
        underline_thickness_mm=0.8, chart_text="{project}",
        clip_content_mode="text", clip_text="ID", clip_text_font="Inter",
        clip_border_width_mm=30.0, bit16=True, compression="zlib")
    data = {"layout_recipe": replace(rec, seed=None).to_dict(),
            "pages": 1, "auto_patches": False}
    t._restore_user_preset(data)
    out = t._manual_layout_panel.get_recipe()
    for f in ("pscale", "indicator_font", "indicator_bold", "underline_mode",
              "underline_thickness_mm", "chart_text", "clip_content_mode",
              "clip_text", "clip_border_width_mm", "bit16", "compression"):
        assert getattr(out, f) == getattr(rec, f), f


def test_editor_carry_back_engine_recipe(qapp, tmp_path):
    """A chart adopted from the editor with an engine channels.json turns the
    engine on and seeds the Manual panel; a non-engine one turns it off (#93)."""
    import json
    t = _tab(qapp)
    t._settings.set("use_chromiq_layout_engine", False)
    rec = LayoutRecipe(instrument="i1", paper="A4", clip_border=True,
                       underline_mode="segments", clip_content_mode="branding")
    ch = tmp_path / "EditedChart.channels.json"
    ch.write_text(json.dumps({"layout": {"engine": "chromiq", "seed": 7,
                                         "recipe": replace(rec, seed=None).to_dict()}}))
    t._carry_engine_recipe_from(ch)
    assert t._settings.get("use_chromiq_layout_engine", False) is True
    assert not t._manual_layout_grp.isHidden()
    out = t._manual_layout_panel.get_recipe()
    assert out.underline_mode == "segments"
    assert out.clip_content_mode == "branding"
    # a chart without an engine recipe turns the engine back off
    t._carry_engine_recipe_from(tmp_path / "missing.channels.json")
    assert t._settings.get("use_chromiq_layout_engine", False) is False
    assert not t._manual_printtarg_grp.isHidden()


def test_preset_auto_toggles_engine(qapp):
    # Engine off; loading a preset WITH a layout_recipe turns it on.
    t = _tab(qapp)
    t._settings.set("use_chromiq_layout_engine", False)
    rec = LayoutRecipe(instrument="i1", paper="A4", clip_border=True)
    t._restore_user_preset({"layout_recipe": replace(rec, seed=None).to_dict(),
                            "pages": 1, "auto_patches": False})
    assert t._settings.get("use_chromiq_layout_engine", False) is True
    assert not t._manual_layout_grp.isHidden()        # engine panel shown

    # Engine on; loading an old/printtarg preset (no layout_recipe) turns it off.
    t._settings.set("use_chromiq_layout_engine", True)
    t._refresh_manual_command_preview()
    t._restore_user_preset({"printtarg_-i": "i1", "printtarg_-p": "A4",
                            "pages": 1, "auto_patches": False})
    assert t._settings.get("use_chromiq_layout_engine", False) is False
    assert not t._manual_printtarg_grp.isHidden()     # printtarg controls shown


def test_named_preset_restores_notes_and_stamp(qapp):
    """chart_notes / stamp_commands round-trip with a preset. The stamp value
    is applied after the engine auto-toggle, which would otherwise reset the
    checkbox to its mode default (mavtop, forum)."""
    t = _tab(qapp)
    t._settings.set("use_chromiq_layout_engine", False)
    rec = LayoutRecipe(instrument="i1", paper="A4", clip_border=True)
    t._restore_user_preset({"layout_recipe": replace(rec, seed=None).to_dict(),
                            "pages": 1, "auto_patches": False,
                            "chart_notes": "Canon / Baryta",
                            "stamp_commands": True})
    assert t._manual_chart_notes_edit.text() == "Canon / Baryta"
    # The engine flipped ON (that defaults the box to unchecked) — the
    # preset's True must survive.
    assert t._manual_stamp_cmd_check.isChecked() is True


def test_preset_without_notes_keys_leaves_fields(qapp):
    """Presets saved before the chart_notes / stamp_commands keys existed
    leave both fields exactly as they are (backward compatibility)."""
    t = _tab(qapp)
    t._manual_chart_notes_edit.setText("keep me")
    t._manual_stamp_cmd_check.setChecked(False)
    t._restore_user_preset({"printtarg_-i": "i1", "printtarg_-p": "A4",
                            "pages": 1, "auto_patches": False})
    assert t._manual_chart_notes_edit.text() == "keep me"
    assert t._manual_stamp_cmd_check.isChecked() is False
