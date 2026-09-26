"""K57: Knut #182 5848511977, for beta 44 (5848514529).

1. THE VERIFICATION MARK (B8-1387). "The star in the "Which presets can be
   used for verification?" window should use another symbol ... Help text and
   text in the window, and in notes, should then not use the word "star"
   relating to function "made for verification"." It is ● now: not an arrow,
   because "▸" already means "N more presets" in the same lists. Create
   Chart's ★ for a BUILT-IN preset stays, and now means only that
   (B8-1364 answered).

2. THE CLIP BORDER'S CONTENT (B8-1388, B8-1389). "Inside that tab
   [Preferences > Chart Layout] the values are defaults, so changing the
   default shall not change the clip border setting." On the ColorMunki,
   SpectroScan and CR30 the Content box WAS the On / Off switch, so a Content
   chosen with the clip border Off switched it On. The kind is kept in the
   recipe's `clip_content_when_on`, and a clip border switched On starts on
   it. And in Create Chart, "selecting anything there shall not reload any
   defaults for the clip-border content frame's fields": measured on screen,
   nothing does; pinned here.

Every test names the mutation that turns it red; each was run red
(~/Desktop/ChromIQ-beta44-proof/k56/mutations-k57.txt).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MARK = "●"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _cat(code: str) -> dict:
    return json.loads((ROOT / f"data/i18n/{code}.json").read_text(
        encoding="utf-8"))


# --------------------------------------------------------------------------
# 1. the verification mark
# --------------------------------------------------------------------------
def test_a_preset_made_for_verification_wears_the_circle_not_the_star(qapp):
    """The list row and the detail pane.

    MUTATION, proven red: put "★  " back as the row prefix in `_columns`."""
    from ui.dialogs import preset_verification_dialog as PVD
    row = PVD.PresetRow(group="i1Pro", label="A4-156p", chart=None,
                        patches=156, pages=1, builtin=True, starred=True)
    cols = PVD.PresetVerificationDialog._columns(
        type("D", (), {})(), row)
    assert cols[0].startswith(MARK + "  "), cols[0]
    assert "★" not in cols[0]
    text = " ".join(ln.text for ln in PVD.detail_lines(row))
    assert MARK + "  Made for verification." in text
    assert "★" not in text


def test_no_text_about_made_for_verification_says_star():
    """In English and in German: no catalogue key or German value that is
    about the verification mark says ★, "star" or "Stern"; the built-in
    presets' ★ stays.

    MUTATION, proven red: set the help card's title back to "What the ★
    means, and why it does not move"."""
    de = _cat("de")
    about = [k for k in de if "made for verification" in k.lower()
             or "made for verification" in k.lower().replace("made ", "made ")
             or k.startswith(("What the ", "A window on the Create Chart tab, "
                              "shown on verification runs only",
                              "Opens a list of every chart preset"))]
    assert about, "the texts about the mark are gone"
    for k in about:
        assert "★" not in k and not re.search(r"\bstars?\b", k, re.I), k
        v = de[k]
        assert "★" not in v and "Stern" not in v, v
    assert "What the ● means, and why it does not move" in de
    # the built-in mark is untouched
    assert any("built-in presets (marked ★)" in k for k in de)
    from ui.tabs.tab_chart import TC918_PRESET_LABEL
    assert TC918_PRESET_LABEL.startswith("★")


def test_the_presets_button_help_names_the_circle(qapp):
    """The tooltip of Create Chart's presets button (B8-1341): text only.

    MUTATION, proven red: "A ★ marks a chart made for verification" back in
    `tab_chart.py`."""
    src = (ROOT / "ui/tabs/tab_chart.py").read_text(encoding="utf-8")
    src = re.sub(r'"\s*\n\s*"', "", src)
    assert "A ● marks a chart made for verification: one or two printed" in src
    assert "A ★ marks a chart made for verification" not in src


# --------------------------------------------------------------------------
# 2. the clip border's content
# --------------------------------------------------------------------------
def _prefs_panel():
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    return LayoutOptionsPanel(None, clip_content_always_shown=True)


@pytest.mark.parametrize("instr", ["CM", "SS", "CR30"])
def test_a_content_chosen_in_preferences_with_the_clip_border_off_keeps_it_off(
        qapp, instr):
    """B8-1388. Content picked while Off: still Off, the recipe says so, and
    the kind is kept for when it is switched On, which then starts on it.

    MUTATION, proven red: drop the `_clip_held_off` test from
    `clip_enabled` (the Content switches the clip border On again)."""
    from workflow.layout_engine.presets import default_recipe
    p = _prefs_panel()
    try:
        r = default_recipe(instr, "A4")
        r.clip_content_mode = "off"
        p.set_recipe(r)
        qapp.processEvents()
        assert not p.clip_enabled()
        for kind in ("text", "branding", "image"):
            p.clip_content_mode.setCurrentIndex(
                p.clip_content_mode.findData(kind))
            qapp.processEvents()
            assert not p.clip_enabled(), f"{instr}: {kind} switched it On"
            got = p.get_recipe()
            assert got.clip_content_mode == "off"
            assert got.clip_content_when_on == kind
        # a stored Off recipe comes back Off, showing the kind it keeps
        p.set_recipe(p.get_recipe(default_recipe(instr, "A4")))
        qapp.processEvents()
        assert not p.clip_enabled()
        assert p.clip_content_mode.currentData() == "image"
        p.set_clip_enabled(True)
        qapp.processEvents()
        assert p.clip_enabled()
        assert p.get_recipe().clip_content_mode == "image"
        p.set_clip_enabled(False)
        qapp.processEvents()
        assert p.get_recipe().clip_content_mode == "off"
        assert p.get_recipe().clip_content_when_on == "image"
    finally:
        p.deleteLater()
        qapp.processEvents()


def test_create_chart_switched_on_starts_on_the_kept_content(qapp):
    """B8-1388. A recipe that keeps "branding" for its clip border, loaded
    Off in Create Chart and switched On there, starts on the branding (it
    started on the Notes box whatever was meant, B8-1362's limit).

    MUTATION, proven red: seed `set_clip_enabled` with "notes" again."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from workflow.layout_engine.presets import default_recipe
    p = LayoutOptionsPanel(None, with_selectors=True)
    try:
        p.instr.setCurrentIndex(p.instr.findData("CM"))
        qapp.processEvents()
        r = default_recipe("CM", "A4")
        r.clip_content_mode = "off"
        r.clip_content_when_on = "branding"
        p.set_recipe(r)
        qapp.processEvents()
        assert not p.clip_enabled()
        assert p._clip_content_grp.isHidden(), "Create Chart shows it while Off"
        p.set_clip_enabled(True)
        qapp.processEvents()
        assert p.clip_content_mode.currentData() == "branding"
    finally:
        p.deleteLater()
        qapp.processEvents()


def test_create_chart_content_changes_reload_no_other_field(qapp):
    """B8-1389. Clip border On, the frame's fields set by hand, Content
    stepped through every kind: Side, Flip, Text and Font never change. Size
    reads "auto" while the Notes box is chosen (it sizes itself, #125) and
    the typed size is back on leaving it.

    MUTATION, proven red: make `_on_clip_content_changed` reset the Side to
    "left"."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(None, with_selectors=True)
    try:
        p.instr.setCurrentIndex(p.instr.findData("CM"))
        qapp.processEvents()
        p.set_clip_enabled(True)
        p.clip_content_mode.setCurrentIndex(p.clip_content_mode.findData("text"))
        p.clip_side.setCurrentIndex(p.clip_side.findData("right"))
        p.clip_flip_180.setChecked(True)
        p.clip_text.setPlainText("typed by hand")
        p.clip_text_font.setCurrentIndex(min(2, p.clip_text_font.count() - 1))
        p.clip_text_size.setValue(9.0)
        qapp.processEvents()
        base = (p.clip_side.currentData(), p.clip_flip_180.isChecked(),
                p.clip_text.toPlainText(), p.clip_text_font.currentText())
        for kind in ("branding", "notes", "image", "text"):
            p.clip_content_mode.setCurrentIndex(
                p.clip_content_mode.findData(kind))
            qapp.processEvents()
            now = (p.clip_side.currentData(), p.clip_flip_180.isChecked(),
                   p.clip_text.toPlainText(), p.clip_text_font.currentText())
            assert now == base, (kind, base, now)
            assert p.clip_text_size.value() == (0.0 if kind == "notes" else 9.0)
    finally:
        p.deleteLater()
        qapp.processEvents()
