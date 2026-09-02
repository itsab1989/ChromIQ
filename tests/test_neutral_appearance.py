"""Neutral — the third appearance, switched on.

A light-grey working environment with no colour anywhere in the interface,
built to the approved design handoff (`Register: Balanced`, `Surface logic:
Stacked`, accent Draft 1 "Index" — one `ACTION` value on every accent surface).

What is proved here, in order:

* Neutral is registered in **all five places** switching it on requires, and
  each one is a completeness check rather than a spot check, so a sixth place
  that grows later fails here and not on a user's screen;
* **the values are the handoff's, to the byte** — every token, and every one of
  the fifteen contrast ratios the handoff printed, recomputed from the
  constants this module actually exports;
* **the three rules hold**: nothing lighter than its ground, no inverted text
  anywhere, and low contrast means "disabled" and nothing else;
* the seven two-entry palette tables each carry a third row, and each component
  really reaches it — the mutation is: hand the component ``"neutral"`` and
  require the colours to differ from Dark's;
* the splash paints the wordmark without the magenta, in both splash styles;
* the combo entry exists and is translated into all twelve languages.

APPEARANCE IS SET BY PALETTE AND PER-WIDGET STYLESHEET, NEVER BY
``apply_appearance``. An app-wide ``setStyleSheet`` in a test re-polishes every
widget the suite has alive, and under xdist it crashed the worker when a theme
suite shared a process with another (CLAUDE.md, and the two commits before
this one). The pixel measurements below style the widget under test, which
measures the same thing.
"""
from __future__ import annotations

import json
import pathlib

import pytest
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QLineEdit, QPushButton, QWidget

import ui.theme as theme
from ui import neutral_styles as N

ROOT = pathlib.Path(__file__).resolve().parents[1]
NEUTRAL = theme.APPEARANCE_NEUTRAL


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ======================================================================
# 0. Contrast, computed the way the handoff computed it
# ======================================================================

def _luminance(hexc: str) -> float:
    h = hexc.lstrip("#")
    parts = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
           for c in parts]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio between two hex colours."""
    la, lb = _luminance(a), _luminance(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


# ======================================================================
# 1. THE FIVE PLACES — switching Neutral on
# ======================================================================

def test_neutral_is_a_valid_appearance_setting():
    """What the Preferences combo may store."""
    assert NEUTRAL in theme.VALID_APPEARANCES


def test_neutral_is_a_concrete_appearance():
    """What ``accept_mode`` admits and ``active_mode`` may answer."""
    assert NEUTRAL in theme.CONCRETE_APPEARANCES
    assert theme.accept_mode(NEUTRAL) == NEUTRAL
    assert theme.resolve_mode(NEUTRAL) == NEUTRAL


def test_every_concrete_appearance_has_all_four_rows():
    """The completeness guard. Four tables have to learn a new appearance and
    every one of them is silent about a missing row in a different, wrong way:
    no fingerprint reads as Light, no ground hangs a black title bar over a
    light window, no style paints the dark stylesheet, no palette crashes."""
    for table, name in ((theme._FINGERPRINTS, "_FINGERPRINTS"),
                        (theme._DARK_GROUND, "_DARK_GROUND"),
                        (theme._APPEARANCE_STYLE, "_APPEARANCE_STYLE")):
        missing = [m for m in theme.CONCRETE_APPEARANCES if m not in table]
        assert missing == [], f"no {name} row for {missing}"


def test_neutral_declares_a_light_ground():
    """`mode == "light"` would have hung a black native title bar over it."""
    assert theme.has_dark_ground(NEUTRAL) is False


def test_auto_never_resolves_to_neutral(app):
    """The OS reports light or dark and has no third scheme. Neutral is only
    ever reached by asking for it by name — which is what the tooltip says."""
    assert theme.resolve_mode(theme.APPEARANCE_AUTO) in (
        theme.APPEARANCE_LIGHT, theme.APPEARANCE_DARK)


def test_active_mode_identifies_the_neutral_palette(app):
    """At L* 90 every lightness threshold the app ever used says "light"."""
    pal = N.make_neutral_palette()
    assert pal.color(QPalette.ColorRole.Window).lightness() > 150
    assert theme.active_mode(pal) == NEUTRAL


def test_apply_appearance_pairs_the_neutral_sheet_with_the_neutral_palette():
    """The dispatch was ``LIGHT_STYLESHEET if mode == "light" else
    APP_STYLESHEET``, which would have dressed a light-grey palette in the dark
    stylesheet. It is a table now; this is the row."""
    sheet, make_palette = theme._APPEARANCE_STYLE[NEUTRAL]
    assert sheet is N.NEUTRAL_STYLESHEET
    assert make_palette is N.make_neutral_palette
    # …and no two appearances share a sheet.
    sheets = [s for s, _ in theme._APPEARANCE_STYLE.values()]
    assert len(set(map(id, sheets))) == len(sheets)


# ======================================================================
# 2. THE VALUES ARE THE HANDOFF'S
# ======================================================================

#: The handoff's design-token table, with the ONE change the owner has made to
#: it since. Nothing in the app may re-derive these; the ratios below were
#: computed from them.
#:
#: BG_PANEL was #ebebeb (L* 93) and BG_SURFACE #f5f5f5 (L* 97) — the handoff's
#: "Stacked" surface logic. The owner looked at the shipped build on 2026-09-02
#: and collapsed both onto the window value: *"it looks like every section in
#: every tab is a little lighter than the background of the main window. should
#: be the same color."* His instruction outranks the handoff. Every contrast
#: below is recomputed against #e2e2e2, and the pairs that used to be told
#: apart by a step in value are told apart by an edge and a weight instead —
#: see tests/test_neutral_ground_and_rule.py.
HANDOFF_TOKENS = {
    "BG_WINDOW":  "#e2e2e2",
    "BG_PANEL":   "#e2e2e2",
    "BG_SURFACE": "#e2e2e2",
    "BG_INPUT":   "#ffffff",
    "BG_VIEWER":  "#d4d4d4",
    "BORDER":     "#b6b6b6",
    "BORDER_HI":  "#2f2f2f",
    "TEXT_MAIN":  "#101010",
    "TEXT_DIM":   "#232323",
    "TEXT_FAINT": "#3f3f3f",
    "ACTION":     "#101010",
    "ON_ACTION":  "#e8e8e8",
    "DISABLED":   "#c4c4c4",
}

#: The handoff's "Contrast, as designed" table, verbatim.
#: RECOMPUTED against the one ground. The right-hand column of the handoff's
#: own table, for the pairs that moved, was 15.96 / 17.45 / 13.18 / 14.42 /
#: 8.83 / 15.96 / 11.23 / 1.70 / 1.46. Nothing that works dropped below 8:1.
HANDOFF_CONTRAST = [
    ("TEXT_MAIN",  "BG_PANEL",   14.69),
    ("TEXT_MAIN",  "BG_SURFACE", 14.69),
    ("TEXT_MAIN",  "BG_INPUT",   19.03),
    ("TEXT_DIM",   "BG_PANEL",   12.13),
    ("TEXT_DIM",   "BG_SURFACE", 12.13),
    ("TEXT_FAINT", "BG_PANEL",    8.13),
    ("TEXT_MAIN",  "BG_WINDOW",  14.69),
    ("TEXT_MAIN",  "BG_VIEWER",  12.84),
    ("ACTION",     "BG_PANEL",   14.69),
    ("ACTION",     "BG_WINDOW",  14.69),
    ("ACTION",     "BG_INPUT",   19.03),
    ("ON_ACTION",  "ACTION",     15.53),
    ("BORDER_HI",  "BG_PANEL",   10.33),
    ("BORDER",     "BG_PANEL",    1.57),
    ("DISABLED",   "BG_PANEL",    1.35),
]


@pytest.mark.parametrize("token,hexc", sorted(HANDOFF_TOKENS.items()))
def test_every_token_is_the_handoff_value(token, hexc):
    assert getattr(N, f"NM_{token}").lower() == hexc


@pytest.mark.parametrize("fg,bg,ratio", HANDOFF_CONTRAST,
                         ids=[f"{f}_on_{b}" for f, b, _ in HANDOFF_CONTRAST])
def test_the_handoff_contrast_table_still_holds(fg, bg, ratio):
    got = contrast(getattr(N, f"NM_{fg}"), getattr(N, f"NM_{bg}"))
    assert abs(got - ratio) < 0.02, f"{fg} on {bg}: {got:.2f}, expected {ratio}"


def test_every_token_is_a_true_neutral():
    """R = G = B, without exception. The chrome sits beside the TIFF preview
    and the 3D gamut viewer, and a tinted chrome biases the judgement of
    coloured content — which is the specific complaint about the light theme."""
    for token, hexc in HANDOFF_TOKENS.items():
        c = QColor(getattr(N, f"NM_{token}"))
        assert c.red() == c.green() == c.blue(), f"NM_{token} is tinted"


# ======================================================================
# 3. THE THREE RULES
# ======================================================================

_GROUNDS = ("BG_WINDOW", "BG_PANEL", "BG_SURFACE", "BG_INPUT", "BG_VIEWER")
_MARKS = ("ACTION", "BORDER", "BORDER_HI", "TEXT_MAIN", "TEXT_DIM",
          "TEXT_FAINT", "DISABLED")


@pytest.mark.parametrize("mark", _MARKS)
def test_rule_1_nothing_is_ever_lighter_than_its_ground(mark):
    """On a panel at L* 93 there is no headroom above: white on the panel
    reaches 1.2:1. Every accent, rule, ring and indicator is DARKER than what
    it sits on, without exception."""
    m = QColor(getattr(N, f"NM_{mark}")).lightness()
    for ground in _GROUNDS:
        g = QColor(getattr(N, f"NM_{ground}")).lightness()
        assert m < g, f"NM_{mark} (L {m}) is not darker than NM_{ground} (L {g})"


def test_rule_2_no_text_token_is_light():
    """All text is dark. There is no inverted text anywhere.

    This was the single recurring bug while building the reference: a light
    constant painted onto a surface that is now light gives 1.78:1. The one
    sanctioned light value is ON_ACTION, and it is a label on a FILL, not an
    inversion of the theme — so it is excluded here by name and pinned by the
    ON_ACTION-on-ACTION row of the contrast table instead.
    """
    for token in ("TEXT_MAIN", "TEXT_DIM", "TEXT_FAINT", "ACTION"):
        c = QColor(getattr(N, f"NM_{token}"))
        assert c.lightness() < 128, f"NM_{token} is a light value"


def test_rule_2_the_dark_theme_is_not_the_source_of_any_value():
    """Nothing is carried over. Every value here is chosen for a light ground;
    a dark-theme constant arriving by copy-paste is exactly the fault."""
    from ui import styles
    dark = {v.lower() for k, v in vars(styles).items()
            if isinstance(v, str) and v.startswith("#") and len(v) == 7}
    mine = {getattr(N, f"NM_{t}").lower() for t in HANDOFF_TOKENS}
    shared = dark & mine
    # #101010 is genuinely in both: it is the dark theme's BG_DARK and this
    # theme's ink. That is a coincidence of two hexes, not a carried value —
    # one is a background there and a foreground here.
    assert shared <= {"#101010"}, f"carried over from the dark theme: {shared}"


def test_rule_3_only_the_disabled_token_is_low_contrast():
    """Low contrast means "disabled" and nothing else. Nothing that WORKS may
    be faint — which is the trap the brief was most worried about, and the
    reason this theme's "tertiary" is dark ink at 8.83:1 rather than a pale
    grey like the light theme's."""
    working = ("TEXT_MAIN", "TEXT_DIM", "TEXT_FAINT", "ACTION", "BORDER_HI")
    for token in working:
        r = contrast(getattr(N, f"NM_{token}"), N.NM_BG_PANEL)
        assert r >= 4.5, f"NM_{token} is only {r:.2f}:1 on the panel"
    assert contrast(N.NM_DISABLED, N.NM_BG_PANEL) < 2.0
    # BORDER is not text — it is a hairline whose job is separation, and the
    # handoff prices it at 1.70:1 deliberately.
    assert contrast(N.NM_BORDER, N.NM_BG_PANEL) < 2.0


def test_the_stylesheet_carries_no_hue():
    """A single tinted literal left in the sheet undoes the whole theme."""
    import re
    offenders = []
    for hexc in re.findall(r"#[0-9a-fA-F]{6}\b", N.NEUTRAL_STYLESHEET):
        c = QColor(hexc)
        if not (c.red() == c.green() == c.blue()):
            offenders.append(hexc)
    assert offenders == [], f"tinted literals in NEUTRAL_STYLESHEET: {offenders}"


def test_the_stylesheet_sets_no_widget_background():
    """The invariant the light theme has always had: an app-wide
    ``QWidget { background: … }`` paints over the masthead rail and over every
    GroupBox surface. See tests/test_bar_sits_on_the_masthead_rail.py."""
    import re
    m = re.search(r"(?m)^QWidget \{(.*?)\}", N.NEUTRAL_STYLESHEET, re.S)
    assert m, "the QWidget rule moved; check whether it now sets a background"
    assert "background" not in m.group(1)


# ======================================================================
# 4. WHAT IS ACTUALLY PAINTED — measured from pixels, not from constants
# ======================================================================
# This project has shipped a wrong colour before because a check read the model
# while the screen showed something else. These grab the widget.

def _ink_and_ground(widget: QWidget) -> tuple[QColor, QColor]:
    """(darkest pixel, most common pixel) of a widget's own grab."""
    img = widget.grab().toImage()
    counts: dict[int, int] = {}
    darkest = None
    for y in range(img.height()):
        for x in range(img.width()):
            c = QColor(img.pixel(x, y))
            counts[c.rgb()] = counts.get(c.rgb(), 0) + 1
            if darkest is None or c.lightness() < darkest.lightness():
                darkest = c
    ground = QColor(max(counts, key=counts.get))
    return darkest, ground


def test_a_painted_button_is_dark_ink_on_a_light_fill(app):
    btn = QPushButton("Build Profile")
    btn.setPalette(N.make_neutral_palette())
    btn.setStyleSheet(N.NEUTRAL_STYLESHEET)
    btn.resize(160, 32)
    ink, ground = _ink_and_ground(btn)
    assert ground.name() == N.NM_BG_WIDGET, ground.name()
    assert ink.lightness() < 60, f"the label is not ink: {ink.name()}"
    assert contrast(ink.name(), ground.name()) >= 7.0
    btn.deleteLater()


def test_a_painted_primary_button_is_the_one_sanctioned_inversion(app):
    """ON_ACTION on ACTION, 15.53:1 — a label on a FILL. The rest of the theme
    stays dark-on-light; this button is the exception the handoff prices."""
    btn = QPushButton("Start")
    btn.setObjectName("primary")
    btn.setPalette(N.make_neutral_palette())
    btn.setStyleSheet(N.NEUTRAL_STYLESHEET)
    btn.resize(160, 32)
    _, ground = _ink_and_ground(btn)
    assert ground.name() == N.NM_ACTION, ground.name()
    btn.deleteLater()


def test_a_painted_field_is_dark_ink_on_white(app):
    ed = QLineEdit("300 patches")
    ed.setPalette(N.make_neutral_palette())
    ed.setStyleSheet(N.NEUTRAL_STYLESHEET)
    ed.resize(200, 30)
    ink, ground = _ink_and_ground(ed)
    assert ground.name() == N.NM_BG_INPUT
    assert contrast(ink.name(), ground.name()) >= 7.0
    ed.deleteLater()


def test_nothing_painted_anywhere_carries_a_hue(app):
    """Scan the real pixels of a small tree of styled controls. A tinted value
    that survived into a paint path shows up here and nowhere else."""
    host = QWidget()
    host.setPalette(N.make_neutral_palette())
    host.setStyleSheet(N.NEUTRAL_STYLESHEET)
    from PyQt6.QtWidgets import (QCheckBox, QComboBox, QGroupBox, QLabel,
                                 QRadioButton, QVBoxLayout)
    box = QGroupBox("Chart", host)
    lay = QVBoxLayout(box)
    for w in (QLabel("Patches"), QLineEdit("918"), QComboBox(),
              QCheckBox("Randomise"), QRadioButton("16 bit"),
              QPushButton("Generate")):
        lay.addWidget(w)
    outer = QVBoxLayout(host)
    outer.addWidget(box)
    host.resize(260, 260)
    img = host.grab().toImage()
    tinted = set()
    for y in range(img.height()):
        for x in range(img.width()):
            c = QColor(img.pixel(x, y))
            # Antialiasing between two neutrals stays neutral; allow 8/255 for
            # subpixel text rendering, which can tint an edge pixel slightly.
            if max(c.red(), c.green(), c.blue()) - min(c.red(), c.green(),
                                                       c.blue()) > 8:
                tinted.add(c.name())
    assert not tinted, f"hued pixels painted under Neutral: {sorted(tinted)[:8]}"
    host.deleteLater()


# ======================================================================
# 5. THE SEVEN PALETTE TABLES
# ======================================================================
# THE MUTATION: hand the component "neutral" and require the colours it then
# holds to differ from the ones it holds for "dark". A table that folded — or
# a third row that was pasted from the dark one — fails this and only this.

def _masthead():
    from ui.masthead_header import MastheadHeader
    return MastheadHeader()


def _tab_bar():
    from ui.spectrum_tab_bar import SpectrumTabBar
    return SpectrumTabBar()


def _tools_popup():
    from ui.tools_popup import ToolsPopup
    return ToolsPopup()


def _preset_popup():
    from ui.builtin_preset_popup import BuiltinPresetPopup
    return BuiltinPresetPopup([("i1Pro", [("TC9.18", "tc918")])])


TABLES = [
    ("MastheadHeader", _masthead),
    ("SpectrumTabBar", _tab_bar),
    ("ToolsPopup", _tools_popup),
    ("BuiltinPresetPopup", _preset_popup),
]


@pytest.mark.parametrize("name,build", TABLES, ids=[n for n, _ in TABLES])
def test_a_palette_table_reaches_its_neutral_row(app, name, build):
    obj = build()
    obj.set_appearance("dark")
    dark = dict(obj._palette)
    obj.set_appearance(NEUTRAL)
    got = dict(obj._palette)
    assert obj._mode == NEUTRAL
    assert got != dark, f"{name} is still painting Dark under Neutral"
    # …and it is not the LIGHT row either — a third appearance that quietly
    # borrows Light's values is the other way to look finished and be wrong.
    obj.set_appearance("light")
    assert got != dict(obj._palette), f"{name} borrowed Light's row"


@pytest.mark.parametrize("name,build", TABLES, ids=[n for n, _ in TABLES])
def test_every_colour_in_a_neutral_row_is_a_true_neutral(app, name, build):
    obj = build()
    obj.set_appearance(NEUTRAL)
    for key, value in obj._palette.items():
        if isinstance(value, str) and value.startswith("#") and len(value) == 7:
            c = QColor(value)
            assert c.red() == c.green() == c.blue(), f"{name}[{key}] = {value}"


def test_the_patch_cube_keeps_its_own_well(app):
    from ui.patch_cube_panel import _THEME
    assert set(_THEME) >= set(theme.CONCRETE_APPEARANCES)
    assert _THEME[NEUTRAL] != _THEME["dark"]
    assert _THEME[NEUTRAL]["bg"] == N.NM_BG_VIEWER


def test_the_scroll_fades_do_not_fade_to_black(app):
    """`_SURFACES` was a (dark, light) TUPLE unpacked positionally, so a third
    appearance took the dark value: a black band across the top and bottom of
    every scroll area in a light-grey app."""
    from ui.fade_scroll import _SURFACES, FadeScrollArea
    for surface, table in _SURFACES.items():
        assert NEUTRAL in table, surface
        assert QColor(table[NEUTRAL]).lightness() > 200, surface
    area = FadeScrollArea(surface="panel")
    area.set_appearance(NEUTRAL)
    assert area._top_fade._color.name() == N.NM_BG_PANEL
    area.deleteLater()


def test_the_measurement_report_gets_its_own_palette_not_the_light_one():
    """It used to be ``_DARK_REPORT if … == "dark" else _LIGHT_REPORT``, which
    gave Neutral the warm light palette — readable, and carrying green and red
    verdicts in a theme that has no hue."""
    from ui.dialogs.measurement_report_dialog import (_LIGHT_REPORT, _REPORTS,
                                                      _NEUTRAL_REPORT)
    assert set(_REPORTS) >= set(theme.CONCRETE_APPEARANCES)
    assert _REPORTS[NEUTRAL] is _NEUTRAL_REPORT
    assert _NEUTRAL_REPORT != _LIGHT_REPORT
    for key, value in _NEUTRAL_REPORT.items():
        c = QColor(value)
        assert c.red() == c.green() == c.blue(), f"{key} = {value}"


def test_the_pdf_report_keeps_its_own_palette_whatever_the_screen_theme():
    """The report leaves the building, gets printed, and is read by someone who
    never chose an appearance. The screen theme has no jurisdiction over it."""
    import inspect
    from ui.dialogs import measurement_report_dialog as m
    src = inspect.getsource(m.MeasurementReportDialog._report_body_html)
    assert "_LIGHT_REPORT if for_pdf" in src


# ======================================================================
# 6. THE SPLASH — both styles
# ======================================================================

MAGENTA = "#ff4573"


def _wordmark_pixels(pm):
    """Every distinct colour in the band the wordmark is drawn in."""
    img = pm.toImage()
    seen: dict[str, int] = {}
    y0, y1 = int(img.height() * 0.30), int(img.height() * 0.55)
    for y in range(y0, y1):
        for x in range(img.width()):
            c = QColor(img.pixel(x, y))
            seen[c.name()] = seen.get(c.name(), 0) + 1
    return seen


def test_the_neutral_splash_drops_the_magenta_wordmark(app):
    """On the frame the magenta measures 2.55:1 — it was not carrying the mark
    on a light ground. "Chrom" goes to TEXT_FAINT and "IQ" to TEXT_MAIN; the
    italic already separates them, and that is the larger contrast step."""
    from ui.splash import make_splash_pixmap
    seen = _wordmark_pixels(make_splash_pixmap(NEUTRAL, "v9.9.9"))
    assert MAGENTA not in seen
    assert seen.get(N.NM_TEXT_FAINT, 0) > 100, "no 'Chrom' in TEXT_FAINT"
    assert seen.get(N.NM_TEXT_MAIN, 0) > 100, "no 'IQ' in TEXT_MAIN"
    assert seen.get(N.NM_BG_WINDOW, 0) > 1000, "the splash ground is not BG_WINDOW"


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_shipped_splashes_keep_their_magenta(app, mode):
    """Light and Dark are untouched. The accent moved from a module constant
    into the palette table; their rows still name the magenta."""
    from ui.splash import make_splash_pixmap
    assert MAGENTA in _wordmark_pixels(make_splash_pixmap(mode, "v9.9.9"))


@pytest.mark.parametrize("plain", [True, False], ids=["plain", "classic"])
def test_both_splash_styles_render_neutral(app, plain):
    """PlainSplash and ClassicSplash — the second is behind the "Classic splash
    screen" setting, and is the escape hatch a user reaches for when the splash
    misbehaves, so it must not be the one place the magenta survives."""
    from ui.splash import make_splash
    splash = make_splash(NEUTRAL, "v9.9.9", plain=plain)
    try:
        pm = splash._pm if plain else splash.pixmap()
        assert MAGENTA not in _wordmark_pixels(pm)
    finally:
        splash.finish(None)
        splash.deleteLater()


def test_the_masthead_wordmark_accent_is_a_palette_key_not_a_global():
    """``_ACCENT`` painted "IQ" in every appearance. It is a per-appearance
    value now — and the two that ship still name the same magenta, so nothing
    moved for them."""
    from ui.masthead_header import _ACCENT, _PALETTES
    assert _PALETTES["light"]["wordmark_accent"] == _ACCENT
    assert _PALETTES["dark"]["wordmark_accent"] == _ACCENT
    assert _PALETTES[NEUTRAL]["wordmark_accent"] == N.NM_TEXT_MAIN
    assert _PALETTES[NEUTRAL]["wordmark"] == N.NM_TEXT_FAINT


# ======================================================================
# 7. PREFERENCES — where the owner switches it on
# ======================================================================

def test_the_appearance_combo_offers_neutral(app, qapp):
    from ui.dialogs.settings_dialog import SettingsDialog
    import inspect
    src = inspect.getsource(SettingsDialog)
    assert 'addItem(tr("Neutral"),      "neutral")' in src, (
        "the Preferences appearance combo no longer offers Neutral")
    # …and the three that shipped keep their positions.
    order = [m for m in ('"auto"', '"light"', '"dark"', '"neutral"')
             if m in src]
    assert order == ['"auto"', '"light"', '"dark"', '"neutral"']


@pytest.mark.parametrize(
    "code", sorted(p.stem for p in (ROOT / "data" / "i18n").glob("*.json")))
def test_the_combo_entry_is_translated_everywhere(code):
    with open(ROOT / "data" / "i18n" / f"{code}.json", encoding="utf-8") as f:
        catalog = json.load(f)
    assert catalog.get("Neutral"), f"[{code}] no translation for 'Neutral'"
    tip = next((v for k, v in catalog.items()
                if k.startswith("Switches the entire app")), None)
    assert tip, f"[{code}] the appearance tooltip is missing"
    assert catalog["Neutral"] in tip, (
        f"[{code}] the tooltip does not mention the Neutral entry by its own "
        f"translated name")
