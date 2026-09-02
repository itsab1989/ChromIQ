"""The controls a person touches, in the Neutral appearance.

Three faults the owner reported by eye are pinned here as assertions:

1. **Preferences checkboxes were backwards** — a ticked-and-enabled box was
   painted `#d0d0d0` (a DARK-theme value) and a ticked-and-disabled one
   `#1f1f1f`, so the box that worked was pale and the one that did not was the
   darkest thing in the window. The rule is the handoff's: enabled controls
   carry a fill and a solid edge, disabled ones have no fill and a dashed edge,
   and low contrast means "disabled" and nothing else.
2. **A light constant on a now-light surface** — the Calculated Patches
   headline, and the same shape everywhere else in this territory.
3. **One accent** — the tab hues and the six tool-dialog accents collapse to
   ACTION; nothing in these windows carries a hue.

**The appearance is set by PALETTE ONLY.** `apply_appearance` sets an app-wide
stylesheet, which re-polishes every live widget and has crashed an xdist worker
when a theme suite shared a process; `active_mode()` reads the palette, which
is all these helpers need.
"""
from __future__ import annotations

import re

import pytest
from PyQt6.QtWidgets import QApplication, QCheckBox

from ui import neutral_styles as nm
from ui.light_styles import make_light_palette
from ui.neutral_styles import make_neutral_palette
from ui.styles import (
    POPUP_HL_TEXT, SPEC_AMBER, SPEC_GREEN, SPEC_MAGENTA, SPEC_VIOLET,
    make_dark_palette,
)
from ui.theme import (
    APPEARANCE_DARK, APPEARANCE_LIGHT, APPEARANCE_NEUTRAL, accent_for,
    active_mode, by_mode, ink_for,
)

HEX = re.compile(r"#([0-9a-fA-F]{6})\b")
MODES = (APPEARANCE_LIGHT, APPEARANCE_DARK, APPEARANCE_NEUTRAL)
_PALETTES = {
    APPEARANCE_LIGHT: make_light_palette,
    APPEARANCE_DARK: make_dark_palette,
    APPEARANCE_NEUTRAL: make_neutral_palette,
}


@pytest.fixture
def wearing(qapp):
    """Put an appearance's PALETTE on the app, and put the old one back.

    Never `apply_appearance`: see the module docstring.
    """
    original = qapp.palette()

    def _wear(mode: str):
        qapp.setPalette(_PALETTES[mode]())
        assert active_mode() == mode, "the palette did not identify as itself"
        return mode

    yield _wear
    qapp.setPalette(original)


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def hues(text: str) -> list[str]:
    """Every hex in `text` that is NOT a true neutral."""
    out = []
    for h in HEX.findall(text):
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        if max(r, g, b) - min(r, g, b) > 0:
            out.append("#" + h)
    return out


def lightness(hexc: str) -> int:
    from PyQt6.QtGui import QColor
    return QColor(hexc).lightness()


# ----------------------------------------------------------------- resolvers
@pytest.mark.parametrize("mode", (APPEARANCE_LIGHT, APPEARANCE_DARK))
@pytest.mark.parametrize("colour", (SPEC_MAGENTA, SPEC_GREEN, SPEC_VIOLET,
                                    SPEC_AMBER, "#ff4573"))
def test_accent_for_hands_light_and_dark_their_colour_back(colour, mode):
    """The property that makes it safe to put in front of every accent site."""
    assert accent_for(colour, mode) == colour


@pytest.mark.parametrize("colour", (SPEC_MAGENTA, SPEC_GREEN, SPEC_VIOLET,
                                    SPEC_AMBER, "#ff4573"))
def test_neutral_has_exactly_one_accent(colour):
    assert accent_for(colour, APPEARANCE_NEUTRAL) == nm.NM_ACTION


@pytest.mark.parametrize("mode", (APPEARANCE_LIGHT, APPEARANCE_DARK))
@pytest.mark.parametrize("colour", ("#1a8f3c", "#c47f17", "#e05252", "#909090"))
def test_ink_for_hands_light_and_dark_their_colour_back(colour, mode):
    assert ink_for(colour, mode) == colour


@pytest.mark.parametrize("level,expected", (("main", nm.NM_TEXT_MAIN),
                                            ("dim", nm.NM_TEXT_DIM),
                                            ("faint", nm.NM_TEXT_FAINT)))
def test_ink_for_neutral_is_dark_ink_at_the_named_level(level, expected):
    assert ink_for("#1a8f3c", APPEARANCE_NEUTRAL, level=level) == expected


def test_no_ink_level_is_faint_enough_to_read_as_disabled():
    """Rule 3: low contrast means disabled and nothing else.

    The faintest thing `ink_for` can return is the tertiary value, and it is
    still 8.83:1 on the panel — far above DISABLED's 1.46:1.
    """
    for level in ("main", "dim", "faint"):
        ink = ink_for("#909090", APPEARANCE_NEUTRAL, level=level)
        assert lightness(ink) < lightness(nm.NM_DISABLED)


@pytest.mark.parametrize("mode,expected", ((APPEARANCE_LIGHT, "L"),
                                           (APPEARANCE_DARK, "D"),
                                           (APPEARANCE_NEUTRAL, "N")))
def test_by_mode_has_room_for_three_answers(mode, expected):
    assert by_mode("L", "D", "N", mode) == expected


# --------------------------------------------------- fault 1: the checkboxes
def test_the_preferences_indicator_is_the_accent_not_a_dark_theme_grey():
    from ui.dialogs.tools_dialogs import _indicator_color

    class _S:
        def get(self, _k, _d=None):
            return "neutral"

    assert _indicator_color(_S()) == nm.NM_ACTION


@pytest.mark.parametrize("setting,expected", (("light", "#1c1b18"),
                                              ("dark", "#d0d0d0")))
def test_the_two_shipped_indicator_values_did_not_move(setting, expected):
    from ui.dialogs.tools_dialogs import _indicator_color

    class _S:
        def __init__(self, v):
            self.v = v

        def get(self, _k, _d=None):
            return self.v

    assert _indicator_color(_S(setting)) == expected


def test_an_enabled_tick_is_darker_than_a_disabled_one():
    """The owner's sentence, as a number.

    *"in preferences activated checkboxes are light grey, disabled one have a
    much darker grey — should be vice versa."* On a light-grey ground the
    enabled fill must be the DARK one.
    """
    from ui.dialogs.tools_dialogs import _disabled_indicator_qss
    enabled_fill = accent_for("#d0d0d0", APPEARANCE_NEUTRAL)
    dis = _disabled_indicator_qss(APPEARANCE_NEUTRAL)
    assert lightness(enabled_fill) < lightness(nm.NM_BG_PANEL)
    # …and the disabled one carries NO fill at all, so it cannot be darker.
    assert "background: transparent" in dis
    assert "dashed" in dis
    assert nm.NM_DISABLED in dis


def test_the_two_shipped_disabled_indicator_rules_did_not_move():
    from ui.dialogs.tools_dialogs import _disabled_indicator_qss
    for mode in (APPEARANCE_LIGHT, APPEARANCE_DARK):
        rule = _disabled_indicator_qss(mode)
        assert "#4a4a4a" in rule
        assert "dashed" not in rule


def test_settings_dialog_disabled_checkbox_has_no_fill_in_neutral(wearing, qapp):
    """The rule the Settings window adds ON TOP of the shared helper."""
    import inspect
    from ui.dialogs.settings_dialog import SettingsDialog
    src = inspect.getsource(SettingsDialog._apply_indicator_theme)
    assert "APPEARANCE_NEUTRAL" in src
    assert "background: transparent" in src
    assert "dashed" in src
    # …and the two shipped branches are still there, untouched.
    assert '("#eeece8", "#d0ccc6")' in src
    assert '("#1f1f1f", "#3a3a3a")' in src


# ------------------------------------------------- fault 3: one accent, no hue
def test_the_dialog_control_sheet_carries_no_hue_in_neutral():
    from ui.dialogs.tools_dialogs import neutral_controls_qss
    qss = neutral_controls_qss(SPEC_GREEN, popup=SPEC_VIOLET,
                               mode=APPEARANCE_NEUTRAL)
    assert hues(qss) == [], f"a hue survived: {hues(qss)}"


@pytest.mark.parametrize("mode", (APPEARANCE_LIGHT, APPEARANCE_DARK))
def test_the_dialog_control_sheet_still_wears_the_tools_own_hue(mode):
    from ui.dialogs.tools_dialogs import neutral_controls_qss
    qss = neutral_controls_qss(SPEC_GREEN, popup=SPEC_VIOLET, mode=mode)
    assert SPEC_GREEN in qss and SPEC_VIOLET in qss


def test_the_combo_popup_highlight_is_a_fill_not_inverted_text():
    from ui.dialogs.tools_dialogs import _popup_pair
    bg, fg = _popup_pair(SPEC_VIOLET, APPEARANCE_NEUTRAL)
    assert (bg, fg) == (nm.NM_ACTION, nm.NM_ON_ACTION)
    # The one sanctioned light-on-dark pairing, and it is on a FILL.
    assert lightness(fg) > lightness(bg)


@pytest.mark.parametrize("mode", (APPEARANCE_LIGHT, APPEARANCE_DARK))
def test_the_combo_popup_highlight_did_not_move(mode):
    from ui.dialogs.tools_dialogs import _popup_pair
    assert _popup_pair(SPEC_VIOLET, mode) == (SPEC_VIOLET, POPUP_HL_TEXT)


# ------------------------------------------------------- the shared fragments
def test_a_primary_button_label_is_on_action_in_neutral():
    from ui.widgets import primary_label
    assert primary_label(APPEARANCE_NEUTRAL) == nm.NM_ON_ACTION
    for mode in (APPEARANCE_LIGHT, APPEARANCE_DARK):
        assert primary_label(mode) == "#0a0a0a"


def test_a_primary_button_never_brightens_under_the_pointer():
    """Rule 1: nothing is ever lighter than its ground — and a hover nobody
    can SEE is not a hover.

    ACTION is L* 5. Darkening it by the coloured appearances' 0.82 gives
    L* 4 — a one-point move, which is why Neutral steps to TEXT_DIM instead.
    Eight points is the floor a difference has to clear to be a state change
    rather than a rounding error.
    """
    from ui.widgets import primary_hover
    fill = accent_for(SPEC_GREEN, APPEARANCE_NEUTRAL)
    hover = primary_hover(fill, APPEARANCE_NEUTRAL)
    assert lightness(hover) < lightness(nm.NM_BG_PANEL)
    assert abs(lightness(hover) - lightness(fill)) >= 8, (
        f"{fill} -> {hover} is not a visible change")


def test_a_disabled_primary_button_loses_its_fill_in_neutral():
    from ui.widgets import disabled_primary_qss
    rule = disabled_primary_qss(SPEC_AMBER, APPEARANCE_NEUTRAL)
    assert hues(rule) == []
    assert "background: transparent" in rule and "dashed" in rule


@pytest.mark.parametrize("mode,fill", ((APPEARANCE_LIGHT, "#e8e6e1"),
                                       (APPEARANCE_DARK, "#1e1e1e")))
def test_the_two_shipped_disabled_button_fills_did_not_move(mode, fill):
    from ui.widgets import disabled_primary_qss
    rule = disabled_primary_qss(SPEC_AMBER, mode)
    assert fill in rule and SPEC_AMBER in rule


@pytest.mark.parametrize("kind,mark", (("error", "border-left: 3px"),
                                       ("warn", "border-bottom: 2px")))
def test_a_banner_is_told_apart_by_shape_in_neutral(kind, mark):
    from ui.widgets import banner_qss
    rule = banner_qss("#ff4573", "rgba(255,69,115,0.12)",
                      APPEARANCE_NEUTRAL, kind=kind)
    assert hues(rule) == []
    assert mark in rule
    assert nm.NM_TEXT_MAIN in rule


@pytest.mark.parametrize("mode", (APPEARANCE_LIGHT, APPEARANCE_DARK))
def test_a_banner_keeps_its_hue_in_the_coloured_appearances(mode):
    from ui.widgets import banner_qss
    rule = banner_qss("#ff4573", "rgba(255,69,115,0.12)", mode)
    assert "#ff4573" in rule and "rgba(255,69,115,0.12)" in rule


# ------------------------------------------------------------- set_ink / reink
def test_set_ink_remembers_what_it_was_asked_for(wearing, qapp):
    from ui.widgets import reapply_ink, set_ink
    wearing(APPEARANCE_DARK)
    box = QCheckBox("x")
    set_ink(box, "#1a8f3c", " font-size: 11px;")
    assert "#1a8f3c" in box.styleSheet()
    assert "font-size: 11px" in box.styleSheet()

    from PyQt6.QtWidgets import QWidget
    host = QWidget()
    box.setParent(host)
    reapply_ink(host, APPEARANCE_NEUTRAL)
    assert hues(box.styleSheet()) == []
    assert nm.NM_TEXT_MAIN in box.styleSheet()
    assert "font-size: 11px" in box.styleSheet()
    reapply_ink(host, APPEARANCE_DARK)
    assert "#1a8f3c" in box.styleSheet()


# ------------------------------------------------------ the painted components
def _grab_has_hue(widget) -> bool:
    img = widget.grab().toImage()
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() < 8:
                continue
            if max(c.red(), c.green(), c.blue()) - \
                    min(c.red(), c.green(), c.blue()) > 6:
                return True
    return False


def test_the_dialog_masthead_stripe_drops_its_hues_in_neutral(wearing, qapp):
    from ui.tab_header import SpectrumStripe
    wearing(APPEARANCE_NEUTRAL)
    s = SpectrumStripe()
    s.resize(200, SpectrumStripe.HEIGHT)
    assert not _grab_has_hue(s)


def test_the_dialog_masthead_stripe_keeps_its_hues_in_light_and_dark(wearing, qapp):
    from ui.tab_header import SpectrumStripe
    for mode in (APPEARANCE_LIGHT, APPEARANCE_DARK):
        wearing(mode)
        s = SpectrumStripe()
        s.resize(200, SpectrumStripe.HEIGHT)
        assert _grab_has_hue(s), f"{mode} lost the spectrum"


def test_the_busy_bar_is_five_action_cells_in_neutral(wearing, qapp):
    from ui.spectrum_progress import SPECTRUM, SpectrumSegmentsBar
    wearing(APPEARANCE_NEUTRAL)
    bar = SpectrumSegmentsBar()
    cells, label, sub = bar._palette()
    assert cells == [nm.NM_ACTION] * len(SPECTRUM)
    assert (label, sub) == (nm.NM_TEXT_DIM, nm.NM_TEXT_FAINT)


def test_the_busy_bar_keeps_the_spectrum_in_light_and_dark(wearing, qapp):
    from ui.spectrum_progress import (LABEL_COLOR, SPECTRUM, SUBLABEL_COLOR,
                                      SpectrumSegmentsBar)
    for mode in (APPEARANCE_LIGHT, APPEARANCE_DARK):
        wearing(mode)
        assert SpectrumSegmentsBar()._palette() == (SPECTRUM, LABEL_COLOR,
                                                    SUBLABEL_COLOR)


def test_every_tooltip_ring_in_the_app_is_one_accent(wearing, qapp):
    from ui.tooltip_button import TooltipButton
    wearing(APPEARANCE_NEUTRAL)
    btn = TooltipButton("t", "b", color=SPEC_VIOLET)
    btn.resize(28, 28)
    assert not _grab_has_hue(btn)


def _contrast(a: str, b: str) -> float:
    def lum(h):
        h = h.lstrip("#")
        parts = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
               for c in parts]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    la, lb = lum(a), lum(b)
    if la < lb:
        la, lb = lb, la
    return round((la + 0.05) / (lb + 0.05), 2)


def test_a_tooltip_icon_that_works_is_not_faint(wearing, qapp):
    """The owner, on the shipped build: *"in preferences neutral mode the
    tooltip icons are too light. the color they currently have would be good
    for a disabled state or something."*

    He was looking at `#d0d0d0`, the DARK theme's indicator, handed to every ⓘ
    in Preferences. Measured on the window it sits on that is **1.19:1** —
    fainter than DISABLED itself. Rule 3: low contrast means "disabled" and
    nothing else, so a ⓘ that works must clear the disabled token by a wide
    margin, not sit below it.
    """
    from PyQt6.QtGui import QColor
    from ui.tooltip_button import TooltipButton
    wearing(APPEARANCE_NEUTRAL)
    btn = TooltipButton("t", "b")
    btn.set_appearance(APPEARANCE_NEUTRAL)
    # What the ⓘ is actually drawn in, whatever was asked for.
    from ui.theme import accent_for
    ink = accent_for(TooltipButton.ACCENT, APPEARANCE_NEUTRAL)
    assert ink == nm.NM_ACTION
    assert _contrast(ink, nm.NM_BG_WINDOW) > 4.5
    # …and the value it used to have is below the DISABLED token, so it was
    # never "a good disabled colour" either — it was fainter than one.
    assert _contrast("#d0d0d0", nm.NM_BG_WINDOW) < _contrast(
        nm.NM_DISABLED, nm.NM_BG_WINDOW)


def test_a_tooltip_ring_keeps_its_hue_in_light_and_dark(wearing, qapp):
    from ui.tooltip_button import TooltipButton
    for mode in (APPEARANCE_LIGHT, APPEARANCE_DARK):
        wearing(mode)
        btn = TooltipButton("t", "b", color=SPEC_VIOLET)
        btn.resize(28, 28)
        assert _grab_has_hue(btn), f"{mode} lost the ⓘ accent"


def test_the_preset_button_glyph_follows_the_appearance(wearing, qapp):
    from ui.builtin_preset_popup import BuiltinPresetButton
    wearing(APPEARANCE_NEUTRAL)
    b = BuiltinPresetButton()
    b.set_appearance(APPEARANCE_NEUTRAL)
    assert not _grab_has_hue(b)
    b.set_appearance(APPEARANCE_DARK)
    assert _grab_has_hue(b), "set_appearance is a no-op again"


# -------------------------------------------------- fault 2: no light constant
def test_the_calculated_patches_mark_is_not_a_hue_in_neutral(wearing, qapp):
    from ui.tabs.tab_chart import TabChart
    wearing(APPEARANCE_NEUTRAL)
    assert hues(TabChart._count_with_accent("484")) == []
    assert nm.NM_ACTION in TabChart._count_with_accent("484")


def test_the_calculated_patches_mark_keeps_its_hue_in_light_and_dark(wearing, qapp):
    from ui.tabs.tab_chart import TabChart
    for mode in (APPEARANCE_LIGHT, APPEARANCE_DARK):
        wearing(mode)
        assert SPEC_MAGENTA in TabChart._count_with_accent("484")


def test_the_big_number_takes_dark_ink_only_in_neutral(wearing, qapp):
    """The real `TabChart.set_appearance`, driven on a stand-in.

    A whole `TabChart` costs ~2 s to construct (CLAUDE.md measures it), and
    none of that is what this asserts. The method is bound to a bare QWidget
    carrying the one attribute it touches, so the code under test is the
    shipped one and nothing else is built.

    In Light and Dark the label gets NO colour of its own: the per-tab pane QSS
    supplies one there and this label must not fight it. In Neutral that same
    branch paints `#ffffff`, so the label overrides it — 1.19:1 is the number
    the owner was looking at.
    """
    from PyQt6.QtWidgets import QLabel, QWidget
    from ui.tabs.tab_chart import TabChart

    class _Stand(QWidget):
        _COUNT_QSS = TabChart._COUNT_QSS
        set_appearance = TabChart.set_appearance

    w = _Stand()
    w._patch_count_lbl = QLabel(w)

    w.set_appearance(APPEARANCE_NEUTRAL)
    sheet = w._patch_count_lbl.styleSheet()
    assert nm.NM_TEXT_MAIN in sheet, sheet
    assert lightness(nm.NM_TEXT_MAIN) < lightness(nm.NM_BG_PANEL)

    for mode in (APPEARANCE_LIGHT, APPEARANCE_DARK):
        w.set_appearance(mode)
        assert "color:" not in w._patch_count_lbl.styleSheet()
    assert "color:" not in TabChart._COUNT_QSS


def test_a_tinted_glyph_on_a_pale_ground_is_dark_ink(wearing, qapp):
    """The icon form of the theme's most-repeated trap: `is_light()` answered
    NO for Neutral, so light line art was drawn on a light-grey panel."""
    from ui.widgets import _dark_glyph_ink, _has_light_ground
    wearing(APPEARANCE_NEUTRAL)
    assert _has_light_ground() is True
    ink = _dark_glyph_ink()
    assert lightness(ink) < lightness(nm.NM_BG_PANEL)
    # …and it is a TRUE neutral. The light theme's #22211f is a warm ink and
    # would put a tint back into a theme whose whole point is that it has none.
    assert hues(ink) == [], f"the glyph ink carries a hue: {ink}"
    wearing(APPEARANCE_LIGHT)
    assert _has_light_ground() is True
    assert _dark_glyph_ink() == "#22211f"
    wearing(APPEARANCE_DARK)
    assert _has_light_ground() is False
