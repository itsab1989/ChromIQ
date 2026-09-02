"""The owner's 2026-09-02 batch on the Neutral appearance, pinned.

Five instructions, all given after looking at the shipped build on screen, and
every one of them overrules something the design handoff specified. They are
written out here in his words because the next person to read the theme file
will otherwise "restore" the handoff:

1. *"for neutral mode i want this indexing lines over every tab gone"* — the
   five-cell Index rule goes from the masthead stripe and from the active tab.
2. *"it looks like every section in every tab is a little lighter than the
   background of the main window. should be the same color."* — the three
   stacked grounds collapse onto one.
3. *"in neutral help cards still get a magenta outline when hovered - maybe
   other items as well when hovered or getting focus?"* — no hue in any
   interaction state.
4. *"the log output field in neutral mode should have a white background"*.
5. *"checkboxes and comboboxes (probably also spinboxes) from deactivated
   options have dotted lines in neutral mode - should be continuous"*.

Plus one measurement he asked about: *"the lower margin of this info box in
print chart tab is thicker than the others"* — it was the box's 2px BORDER_HI
bottom EDGE against three 1px hairlines, not white space.

**LIGHT AND DARK MAY NOT MOVE.** Every change above is inside a Neutral branch,
and the last section here is the guard on that.
"""
from __future__ import annotations

import inspect
import re

import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QTabWidget, QWidget

from ui import index_rule, neutral_styles as N


# ----------------------------------------------------------------------
def _lin(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lum(hexc: str) -> float:
    c = QColor(hexc)
    return 0.2126 * _lin(c.red()) + 0.7152 * _lin(c.green()) + 0.0722 * _lin(c.blue())


def contrast(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def lightness(hexc: str) -> int:
    return QColor(hexc).lightness()


# ======================================================================
# 1. ONE GROUND
# ======================================================================

def test_the_three_grounds_are_one_value():
    """His instruction, as an identity. A section is not "a little lighter"
    than the window; it is the window's own value."""
    assert N.NM_BG_PANEL == N.NM_BG_WINDOW
    assert N.NM_BG_SURFACE == N.NM_BG_WINDOW
    assert N.NM_BG_WINDOW == "#e2e2e2"


def test_the_two_surfaces_that_are_still_allowed_to_differ():
    """Not everything flattened, and the two that did not are deliberate.

    BG_INPUT is white — a field you type into, and now the log well too. And
    BG_VIEWER is a step DOWN, because a white patch on a lighter ground
    disappears and the previews show the user's own colours.
    """
    assert N.NM_BG_INPUT == "#ffffff"
    assert N.NM_BG_VIEWER == "#d4d4d4"
    assert lightness(N.NM_BG_VIEWER) < lightness(N.NM_BG_WINDOW)
    assert lightness(N.NM_BG_INPUT) > lightness(N.NM_BG_WINDOW)


@pytest.mark.parametrize("token", ["NM_BG_WIDGET", "NM_MODE_BG",
                                   "NM_TAB_INACTIVE_BG", "NM_TAB_ACTIVE_BG"])
def test_everything_derived_from_a_ground_is_the_ground(token):
    assert getattr(N, token) == N.NM_BG_WINDOW


def test_the_stylesheet_has_no_second_ground_left_in_it():
    """A literal #ebebeb or #f5f5f5 anywhere in the sheet would be a section
    that did not come along."""
    sheet = N.NEUTRAL_STYLESHEET.lower()
    assert "#ebebeb" not in sheet
    assert "#f5f5f5" not in sheet


# ======================================================================
# 2. THE CONTRAST, RECOMPUTED AGAINST THE ONE GROUND
# ======================================================================

@pytest.mark.parametrize("token", ["NM_TEXT_MAIN", "NM_TEXT_DIM", "NM_TEXT_FAINT",
                                   "NM_ACTION", "NM_BORDER_HI"])
def test_nothing_that_works_became_faint_on_the_darker_ground(token):
    """Rule 3 still holds after the collapse. The worst of these is TEXT_FAINT
    at 8.13:1, down from 8.83:1 on the old panel — a long way above 4.5."""
    r = contrast(getattr(N, token), N.NM_BG_PANEL)
    assert r >= 4.5, f"{token} is only {r:.2f}:1 on the ground"


def test_low_contrast_still_means_disabled_and_nothing_else():
    assert contrast(N.NM_DISABLED, N.NM_BG_PANEL) < 2.0
    # BORDER is a hairline, not text — 1.57:1 on the one ground (was 1.70:1 on
    # the old panel), and it is now the ONLY thing separating a section from
    # its surround, which is why it may not be weakened further.
    r = contrast(N.NM_BORDER, N.NM_BG_PANEL)
    assert 1.4 < r < 2.0, f"{r:.2f}:1"
    assert contrast(N.NM_BORDER, N.NM_BG_PANEL) > contrast(N.NM_DISABLED, N.NM_BG_PANEL)


# ======================================================================
# 3. THE DERIVED STATES THAT HAD TO BE RESCUED
# ======================================================================

def test_hover_and_pressed_step_down_from_the_ground_not_onto_it():
    """THE ONE THAT WOULD HAVE BROKEN SILENTLY.

    Hover was BG_WINDOW and pressed BG_VIEWER, one and two steps under a raised
    BG_SURFACE fill. Collapse the surface and hover IS the fill: a combo
    drop-down, a spin button and a browse button change nothing but their
    background under the pointer, so every one of them would have stopped
    reacting and no test would have said so.
    """
    assert N.NM_BG_HOVER != N.NM_BG_WIDGET, "hover is invisible on a flat ground"
    assert lightness(N.NM_BG_HOVER) < lightness(N.NM_BG_WINDOW)
    assert lightness(N.NM_BG_PRESSED) < lightness(N.NM_BG_HOVER)
    # Both are values from the handoff's own table — no new greys were invented.
    table = {N.NM_BG_WINDOW, N.NM_BG_INPUT, N.NM_BG_VIEWER, N.NM_BORDER,
             N.NM_BORDER_HI, N.NM_TEXT_MAIN, N.NM_TEXT_DIM, N.NM_TEXT_FAINT,
             N.NM_ON_ACTION, N.NM_DISABLED}
    assert N.NM_BG_HOVER in table
    assert N.NM_BG_PRESSED in table


def test_the_popup_hover_row_follows_the_hover_token():
    """Both popups named BG_WINDOW for their hover row, which was a step below
    their BG_SURFACE card until the two became the same colour."""
    from ui import builtin_preset_popup as BP, tools_popup as TP
    for mod in (BP, TP):
        pal = mod._PALETTE_NEUTRAL
        assert pal["hover_bg"] == N.NM_BG_HOVER
        assert pal["hover_bg"] != pal["panel_bg"], (
            f"{mod.__name__}: the hover row is the card it sits on")


def test_the_selected_qss_tab_is_told_apart_by_edge_and_weight():
    """Active and inactive tab backgrounds are one value now, so the QSS tabs
    (Preferences, the tool dialogs) need something that is not a fill."""
    assert N.NM_TAB_ACTIVE_BG == N.NM_TAB_INACTIVE_BG
    m = re.search(r"QTabBar::tab:selected\s*\{(.*?)\}",
                  N.NEUTRAL_STYLESHEET, re.S)
    assert m, "the selected-tab rule has gone"
    rule = m.group(1)
    assert N.NM_BORDER_HI in rule, "the selected tab has no edge of its own"
    assert "font-weight: bold" in rule, "the selected tab has no weight of its own"


# ======================================================================
# 4. THE INDEX RULE IS GONE FROM BOTH SITES OVER THE TABS
# ======================================================================

def test_the_masthead_paints_no_index_rule_in_neutral():
    """Source-level, and named to the METHOD: `paint_index_rule` appears in
    four other modules, so a grep over the file would pass on somebody else's
    line."""
    from ui.masthead_header import MastheadHeader
    src = inspect.getsource(MastheadHeader.paintEvent)
    assert "paint_index_rule" not in src, (
        "the masthead still paints the Index rule")
    assert "use_index_rule" in src, "the Neutral branch has gone entirely"
    assert "NM_BORDER" in src, "the masthead lost its top edge as well"


def test_the_tab_bar_paints_no_index_rule_in_neutral():
    from ui.spectrum_tab_bar import SpectrumTabBar
    src = inspect.getsource(SpectrumTabBar.paintEvent)
    assert "paint_index_rule" not in src, (
        "the active tab still carries the five-cell rule")
    assert "NM_BORDER_HI" in src, "the active tab lost its mark entirely"


def test_the_rule_itself_is_kept_for_the_sites_he_did_not_name(qapp):
    """ui/index_rule.py is NOT deleted. He asked for the lines over the tabs,
    and the Build Profile progress ramp, the splash and the dialog mastheads
    are not over a tab — they are listed in the report for him to rule on.
    """
    assert index_rule.CELLS == 5
    assert callable(index_rule.paint_index_rule)
    from ui import spectrum_progress, splash, tab_header
    for mod in (spectrum_progress, splash, tab_header):
        assert "index_rule" in inspect.getsource(mod), (
            f"{mod.__name__} stopped using the rule — that was not asked for")


def test_the_masthead_step_is_still_pushed_even_though_nothing_draws_it(qapp):
    """HONEST ABOUT DEAD CODE. `set_step` now feeds nothing in any appearance.
    It is kept rather than ripped out, because putting the rule back is one
    line if he changes his mind — but the fact is pinned here so nobody reads
    the surviving call as evidence that something still paints a step."""
    from ui.masthead_header import MastheadHeader
    head = MastheadHeader(version="9.9.9")
    head.set_appearance("neutral")
    head.set_step(4)
    assert head._step == 4
    src = inspect.getsource(MastheadHeader.paintEvent)
    assert "self._step" not in src, (
        "the step is painted again — update this test and the report")


# ======================================================================
# 5. THE LOG WELL IS WHITE
# ======================================================================

def test_the_log_well_is_the_input_white():
    assert N.NM_LOG_BG == N.NM_BG_INPUT == "#ffffff"
    assert contrast(N.NM_LOG_TEXT, N.NM_LOG_BG) > 19.0
    assert f"background: {N.NM_LOG_BG}" in (
        N.NEUTRAL_STYLESHEET[N.NEUTRAL_STYLESHEET.index("QPlainTextEdit#log"):])


def test_every_log_well_in_the_app_is_the_same_one_rule(qapp):
    """He said "the log output field"; there are six of them, and two log wells
    with different grounds is the inconsistency he keeps reporting. They all
    carry objectName "log", so the single QSS rule reaches every one — this
    fails if a tab ever gives its log a private background."""
    import pathlib
    root = pathlib.Path(inspect.getfile(N)).parent.parent
    # The three appearance sheets each own a log background — that is the whole
    # point of them. Anything ELSE that sets one is a tab going its own way.
    THEME_SHEETS = {"neutral_styles.py", "light_styles.py", "styles.py"}
    offenders = []
    for path in (root / "ui").rglob("*.py"):
        if path.name in THEME_SHEETS:
            continue
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"QPlainTextEdit#log\s*\{([^}]*)\}", text):
            if "background" in m.group(1):
                offenders.append(path.name)
    assert offenders == [], f"a private log background in {offenders}"


# ======================================================================
# 6. THE DISABLED EDGE IS CONTINUOUS
# ======================================================================

def test_no_dashed_disabled_edge_survives_anywhere():
    """The handoff's shape for "disabled" was a dashed edge. He removed it.
    Every site is checked, not the three controls he happened to look at."""
    assert "dashed" not in N.NEUTRAL_STYLESHEET

    from ui.dialogs.tools_dialogs import _disabled_indicator_qss
    from ui.dialogs.ti2_relayout_dialog import _dis_ind
    from ui.widgets import disabled_primary_qss
    from ui.theme import APPEARANCE_NEUTRAL

    for rule in (_disabled_indicator_qss(APPEARANCE_NEUTRAL),
                 disabled_primary_qss("#ffb42d", APPEARANCE_NEUTRAL)):
        assert "dashed" not in rule and "solid" in rule, rule

    from ui.dialogs.settings_dialog import SettingsDialog
    src = inspect.getsource(SettingsDialog._apply_indicator_theme)
    assert "dashed" not in src.replace("made it dashed", "")

    src = inspect.getsource(_dis_ind)
    assert "1px solid" in src and "1px dashed" not in src


@pytest.mark.parametrize("selector", [
    "QPushButton:disabled",
    "QPushButton#primary:disabled",
    "QCheckBox::indicator:disabled",
    "QRadioButton::indicator:disabled",
])
def test_disabled_is_still_readable_without_the_dash(selector):
    """What carries "disabled" once the dash is gone: no fill, and the edge and
    label drop to DISABLED. A live field is white; a dead one is the ground."""
    m = re.search(re.escape(selector) + r"\s*\{(.*?)\}", N.NEUTRAL_STYLESHEET, re.S)
    assert m, f"{selector} has gone"
    rule = m.group(1)
    assert "transparent" in rule, f"{selector} kept a fill"
    assert N.NM_DISABLED in rule
    assert "solid" in rule


def test_a_disabled_input_loses_the_white_that_makes_it_look_live():
    """The loudest of the three signals, and the one the dash was never doing."""
    m = re.search(r"QLineEdit:disabled,(.*?)\{(.*?)\}", N.NEUTRAL_STYLESHEET, re.S)
    assert m
    assert N.NM_BG_PANEL in m.group(2)
    assert N.NM_BG_INPUT not in m.group(2)
    assert contrast(N.NM_BG_INPUT, N.NM_BG_PANEL) > 1.25, (
        "a live field no longer stands off a dead one")


# ======================================================================
# 7. THE WARNING BOX HAS FOUR EQUAL EDGES
# ======================================================================

def test_the_warning_box_bottom_edge_matches_the_other_three():
    """*"the lower margin of this info box in print chart tab is thicker than
    the others"*. Measured on the Print Chart notice: top 1px #b6b6b6, bottom
    2px #2f2f2f, and the white space above the first line and below the last
    was 8.5 px on both sides — so it was the edge, not a margin."""
    m = re.search(r"QLabel#warning\s*\{(.*?)\}", N.NEUTRAL_STYLESHEET, re.S)
    assert m
    rule = m.group(1)
    assert "border-bottom" not in rule, "the heavy bottom edge is back"
    assert f"border: 1px solid {N.NM_BORDER}" in rule


def test_the_one_line_banners_keep_their_underline():
    """Deliberately NOT flattened with the box above: an underline works next
    to the text it qualifies, and these banners are one line tall."""
    from ui.theme import APPEARANCE_NEUTRAL
    from ui.widgets import banner_qss
    warn = banner_qss("#ffb42d", "rgba(0,0,0,0)", APPEARANCE_NEUTRAL, kind="warn")
    err = banner_qss("#ff4573", "rgba(0,0,0,0)", APPEARANCE_NEUTRAL, kind="error")
    assert "border-bottom: 2px" in warn
    assert "border-left: 3px" in err


# ======================================================================
# 8. NO HUE IN AN INTERACTION STATE
# ======================================================================

def test_the_help_card_hover_edge_goes_through_the_theme():
    """His report, and the exact line. `_apply_style` is named rather than the
    file, because SPEC_MAGENTA appears a dozen times in that module and most of
    them are correct."""
    from ui.dialogs.welcome_dialog import WorkflowCard
    src = inspect.getsource(WorkflowCard._apply_style)
    hover = [l for l in src.splitlines() if "hover_border =" in l]
    assert hover, "the hover edge has gone"
    assert "accent_for" in "".join(hover), (
        "the card's hover edge is a raw hue again")


@pytest.mark.parametrize("mode,expected", [("neutral", "#101010"),
                                           ("light", "#9f82ff"),
                                           ("dark", "#9f82ff")])
def test_the_picker_and_the_name_box_resolve_their_accent(mode, expected, qapp):
    """`_wear_the_tab_accent` paints the focus ring and the chosen row. Its
    callers hand it a raw `_TAB_COLOR`, which is right — the appearance is
    answered at the one place the value reaches a stylesheet. It was not, so
    Build Profile's cyan came through in a theme with no cyan.

    Both copies are checked: they are the same twenty lines in two modules and
    fixing one is the obvious way to leave the other wrong.
    """
    from PyQt6.QtWidgets import QDialog
    from ui.dialogs import name_prompt as NP, project_picker as PP
    from ui.light_styles import make_light_palette
    from ui.styles import make_dark_palette
    from ui.theme import active_mode

    # PALETTE ONLY, and put the old one back. `apply_appearance` sets an
    # app-wide stylesheet and LEAVES IT THERE — this test did exactly that in
    # its first draft and the marquee's under-stroke test, four files later in
    # the same worker, painted itself in Dark and failed. The palette is all
    # `active_mode()` reads.
    palettes = {"neutral": N.make_neutral_palette,
                "light": make_light_palette,
                "dark": make_dark_palette}
    original = qapp.palette()
    qapp.setPalette(palettes[mode]())
    assert active_mode() == mode, "the palette did not identify as itself"
    try:
        for mod in (NP, PP):
            d = QDialog()
            mod._wear_the_tab_accent(d, "#9f82ff")
            qss = d.styleSheet()
            assert expected in qss, (mod.__name__, mode, qss)
            if mode == "neutral":
                assert "#9f82ff" not in qss
                assert N.NM_ON_ACTION in qss
            else:
                assert "#0a0a0a" in qss, "the shipped on-accent moved"
    finally:
        qapp.setPalette(original)


def test_no_focus_ring_in_the_theme_carries_a_hue():
    for m in re.finditer(r"[^{}]*:focus[^{}]*\{([^}]*)\}", N.NEUTRAL_STYLESHEET):
        for hexc in re.findall(r"#[0-9a-fA-F]{6}\b", m.group(1)):
            c = QColor(hexc)
            assert c.red() == c.green() == c.blue(), f"{hexc} in a focus rule"


# ======================================================================
# 9. LIGHT AND DARK DID NOT MOVE
# ======================================================================

def test_neither_shipped_appearance_asks_for_the_index_rule(qapp):
    for mode in ("light", "dark"):
        assert not index_rule.use_index_rule(mode)


def test_the_tab_bar_still_paints_five_hues_where_it_always_did(qapp):
    """The removal is inside `if index:`; the else branches are the shipped
    code. Proven by painting, not by reading."""
    from ui.spectrum_tab_bar import SpectrumTabBar, SPECTRUM
    tabs = QTabWidget()
    bar = SpectrumTabBar(tabs)
    tabs.setTabBar(bar)
    for name in "12345":
        tabs.addTab(QWidget(), name)
    tabs.resize(1000, 200)
    tabs.show()
    for mode in ("light", "dark"):
        bar.set_appearance(mode)
        tabs.setCurrentIndex(2)
        img = bar.grab().toImage()
        r = bar.tabRect(2)
        x = min(r.x() + r.width() // 2, img.width() - 1)
        assert img.pixelColor(x, r.y() + 1).name() == SPECTRUM[2], (
            f"{mode} lost the active tab's own hue")
    tabs.close()


@pytest.mark.parametrize("sheet_module,dash_expected", [("ui.styles", False),
                                                        ("ui.light_styles", False)])
def test_the_two_shipped_sheets_never_had_the_dash_and_still_do_not(
        sheet_module, dash_expected):
    import importlib
    mod = importlib.import_module(sheet_module)
    sheet = getattr(mod, "APP_STYLESHEET", None) or getattr(mod, "LIGHT_STYLESHEET")
    assert ("dashed" in sheet) is dash_expected
