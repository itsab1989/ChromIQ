"""B8-1362 (Knut #182 5847578917): in Preferences > Chart Layout, where the
defaults are stored, "Clip-border content" is shown and editable with the clip
border Off (the ColorMunki, SpectroScan and CR30 default), with a note that
its fields apply only when the clip border is On. Create Chart's panel keeps
the frame hidden while its chart has no clip border.

On screen: ~/Desktop/ChromIQ-beta44-proof/fixes-8-cr30/prefs-clip/.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication                        # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _panel(always: bool):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    return LayoutOptionsPanel(None, clip_content_always_shown=always)


@pytest.mark.parametrize("instr", ["CM", "SS", "CR30"])
def test_preferences_shows_the_frame_and_the_note_with_the_clip_border_off(
        qapp, instr):
    from workflow.layout_engine.presets import default_recipe
    p = _panel(True)
    try:
        r = default_recipe(instr, "A4")
        r.clip_content_mode = "off"
        p.set_recipe(r)
        qapp.processEvents()
        assert not p.clip_enabled()
        assert not p._clip_content_grp.isHidden(), \
            f"{instr}: the frame is hidden with the clip border Off"
        assert not p._clip_content_note.isHidden()
        assert "only when the clip border is On" in p._clip_content_note.text()
        for w in (p.clip_content_mode, p.clip_side, p.clip_text,
                  p.clip_text_font, p.clip_text_size):
            assert w.isEnabled(), f"{instr}: {w.objectName() or w} greyed"
        # a value set while Off is kept in the recipe that is stored
        p.clip_text.setPlainText("kept while off")
        i = p.clip_side.findData("right")
        if i >= 0:
            p.clip_side.setCurrentIndex(i)
        got = p.get_recipe()
        assert got.clip_content_mode == "off"
        assert got.clip_text == "kept while off"
        if i >= 0:
            assert got.clip_side == "right"
        # and switched On, the clip border takes them
        p.set_clip_enabled(True)
        on = p.get_recipe()
        assert on.clip_content_mode != "off"
        assert on.clip_text == "kept while off"
        if i >= 0:
            assert on.clip_side == "right"
    finally:
        p.deleteLater()
        qapp.processEvents()


def test_create_chart_keeps_the_frame_hidden_with_the_clip_border_off(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(None, with_selectors=True)
    try:
        p.instr.setCurrentIndex(p.instr.findData("CR30"))
        qapp.processEvents()
        p.set_clip_enabled(False)
        qapp.processEvents()
        assert p._clip_content_grp.isHidden()
        assert p._clip_content_note is None, \
            "the Preferences note is built in Create Chart"
        p.set_clip_enabled(True)
        qapp.processEvents()
        assert not p._clip_content_grp.isHidden()
    finally:
        p.deleteLater()
        qapp.processEvents()


def test_preferences_builds_its_panel_with_the_frame_always_shown():
    import inspect
    from ui.dialogs import settings_dialog
    src = inspect.getsource(settings_dialog)
    assert "clip_content_always_shown=True" in src


def test_the_i1pro_off_is_its_own_combination_and_stays_hidden(qapp):
    """On the i1Pro "Off" is the Mode "noclip", a layout combination with no
    clip border at all, so nothing set there could be used: unchanged."""
    from workflow.layout_engine.presets import default_recipe
    p = _panel(True)
    try:
        r = default_recipe("i1", "A4", mode="noclip")
        r.clip_content_mode = "off"
        p.set_recipe(r)
        p._clip = False
        p._update_clip_visibility()
        qapp.processEvents()
        assert p._clip_content_grp.isHidden()
        assert p._clip_content_note.isHidden()
    finally:
        p.deleteLater()
        qapp.processEvents()
