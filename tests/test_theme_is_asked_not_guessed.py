"""The seven sites that used to guess the theme now ask for it.

Seven places worked the active appearance out for themselves by measuring how
light a background was, against three different thresholds (127, 128, 150).
Two appearances can share a lightness, so that is not a question a pixel can
answer — a light-grey third appearance at L* 93 reads as Light to all three
thresholds and would silently load Light's icon sets, marquee colours and tab
helper colours.

These tests do three things:

* prove ``ui.theme.active_mode`` IDENTIFIES each shipped palette rather than
  measuring it, and that the guessing fallback is never reached for one;
* prove each of the seven sites really goes through it — by making
  ``active_mode`` lie and watching every one of them change its mind. A site
  that still measured a pixel would not budge;
* prove the answer can carry a third value, by registering one and showing
  ``active_mode`` returns it where every threshold in the app says "light".
"""
from __future__ import annotations

import pytest
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QGroupBox, QWidget

import ui.theme as theme
from ui.light_styles import make_light_palette
from ui.neutral_styles import make_neutral_palette
from ui.styles import make_dark_palette
from ui.theme import (APPEARANCE_DARK, APPEARANCE_LIGHT, APPEARANCE_NEUTRAL,
                      CONCRETE_APPEARANCES, active_mode)

PALETTES = {APPEARANCE_LIGHT: make_light_palette,
            APPEARANCE_DARK: make_dark_palette,
            APPEARANCE_NEUTRAL: make_neutral_palette}


@pytest.fixture
def app(qapp):
    """The shared QApplication, with its palette put back afterwards.

    Deliberately NOT ``apply_appearance``: that sets an app-wide stylesheet,
    which re-polishes every widget the suite has alive in this worker. It is
    slow (see CLAUDE.md) and it crashed the worker outright when this file
    shared a process with others. The palette is the only thing these sites
    read, and it is what ``apply_appearance`` sets anyway.
    """
    original = qapp.palette()
    yield qapp
    qapp.setPalette(original)


def wear(app, mode: str) -> None:
    """Put the application in `mode` — palette only."""
    app.setPalette(PALETTES[mode]())


@pytest.fixture(params=[APPEARANCE_LIGHT, APPEARANCE_DARK,
                        APPEARANCE_NEUTRAL])
def mode(request, app):
    wear(app, request.param)
    return request.param


# --------------------------------------------------------------- the answer

def test_every_concrete_appearance_has_a_fingerprint():
    """An appearance the table does not know is an appearance that reads as
    another one. This is the guard the third theme depends on."""
    assert set(theme._FINGERPRINTS) == set(CONCRETE_APPEARANCES)


def test_active_mode_identifies_the_shipped_palette_it_is_given(app, mode):
    assert active_mode() == mode


def test_the_guessing_fallback_is_never_reached_for_a_shipped_palette(app, mode):
    """The lightness rule survives only for palettes ChromIQ did not paint."""
    pal = app.palette()
    hits = [role for role in theme._FINGERPRINT_ROLES
            if pal.color(role).rgb() in theme._MODE_BY_RGB[role]]
    assert hits, f"{mode} palette matched no fingerprint role — it was GUESSED"


def test_an_unrecognised_palette_still_gets_the_historical_answer(app):
    """Nothing that works today stops working: a palette from outside the app
    falls back to the same lightness rule the sites used."""
    for window, expected in (("#ffffff", APPEARANCE_LIGHT),
                             ("#000000", APPEARANCE_DARK),
                             ("#c0c0c0", APPEARANCE_LIGHT),
                             ("#404040", APPEARANCE_DARK)):
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, QColor(window))
        pal.setColor(QPalette.ColorRole.WindowText, QColor("#7f0000"))
        assert active_mode(pal) == expected, window


def test_resolve_mode_passes_a_concrete_setting_straight_through(app):
    for concrete in CONCRETE_APPEARANCES:
        assert theme.resolve_mode(concrete) == concrete


# ------------------------------------------------- ready for a third answer

NEUTRAL_BG_WINDOW = "#E2E2E2"   # the handoff's Neutral, L* 90
NEUTRAL_TEXT_MAIN = "#101010"
NEUTRAL_BG_PANEL = "#EBEBEB"    # L* 93 — the value that started this


def test_the_third_appearance_is_one_row_and_it_is_not_read_as_light(app):
    """Neutral SHIPS now, and its row is what keeps it out of Light's answer.

    This test used to register the fingerprint itself, because the theme did
    not exist. It now takes the real palette and proves the same thing twice
    over: every lightness threshold the seven sites ever used calls this
    palette "light", and ``active_mode`` does not.
    """
    pal = make_neutral_palette()
    window = pal.color(QPalette.ColorRole.Window)
    text = pal.color(QPalette.ColorRole.WindowText)
    assert window.name() == NEUTRAL_BG_WINDOW.lower()
    assert text.name() == NEUTRAL_TEXT_MAIN.lower()

    # What the old code would have said, at all three thresholds:
    assert window.lightness() > 150
    assert not QColor(NEUTRAL_BG_PANEL).lightness() < 128
    assert not text.lightness() > 127

    assert active_mode(pal) == APPEARANCE_NEUTRAL

    # …and it is the ROW that does it. Take the row away and the app is back to
    # calling a light-grey theme "light".
    row = theme._FINGERPRINTS.pop(APPEARANCE_NEUTRAL)
    theme._rebuild_fingerprint_index()
    try:
        assert active_mode(pal) == APPEARANCE_LIGHT
    finally:
        theme._FINGERPRINTS[APPEARANCE_NEUTRAL] = row
        theme._rebuild_fingerprint_index()
    assert active_mode(pal) == APPEARANCE_NEUTRAL


# ------------------------------------------- the seven, proven to go through

@pytest.fixture
def lying_theme(monkeypatch, app):
    """Make ``active_mode`` answer the OPPOSITE of the truth.

    Every site that has stopped guessing must change its mind; a site still
    reading a pixel will not notice. ``is_dark`` / ``is_light`` call
    ``active_mode`` through the module globals, so this one patch covers the
    sites that use those too.
    """
    wear(app, APPEARANCE_DARK)

    def _lie(palette=None):
        return APPEARANCE_LIGHT
    monkeypatch.setattr(theme, "active_mode", _lie)
    yield lambda: monkeypatch.undo()


def test_1_bar_icons_disabled_grey_follows_the_answer(app, lying_theme):
    stop_lying = lying_theme
    from ui.bar_icons import delete_button
    btn = delete_button("#9f82ff", "Delete")
    assert btn._disabled_colour() == btn.GREY_ON_LIGHT   # the lie
    stop_lying()      # the app is really on DARK
    assert delete_button("#9f82ff", "D")._disabled_colour() == btn.GREY_ON_DARK


def test_2_cr30_accent_follows_the_answer(app, lying_theme):
    stop_lying = lying_theme
    from ui.cr30_pictograms import ACCENT_DARK, ACCENT_LIGHT, _accent
    w = QWidget()
    assert _accent(w).name() == ACCENT_LIGHT            # the lie
    stop_lying()      # the app is really on DARK
    assert _accent(w).name() == ACCENT_DARK


def test_2b_cr30_ink_is_left_alone_and_still_follows_the_widget(app):
    """``_ink`` decides nothing — it paints with the foreground it is handed.
    It must NOT have been routed through the theme module."""
    from ui.cr30_pictograms import _ink
    wear(app, APPEARANCE_DARK)
    w = QWidget()
    pal = w.palette()
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#ff00ff"))
    w.setPalette(pal)
    assert _ink(w).name() == "#ff00ff"


def test_3_marquee_backdrop_follows_the_answer(app, lying_theme):
    stop_lying = lying_theme
    from ui.scan_grid_marquee import ScanGridMarquee
    mq = ScanGridMarquee()
    assert mq._is_dark() is False                       # the lie
    stop_lying()      # the app is really on DARK
    assert ScanGridMarquee()._is_dark() is True


def test_4_groupbox_surface_follows_the_answer(app, lying_theme):
    stop_lying = lying_theme
    from ui.light_styles import LM_BG_SURFACE
    from ui.widgets import _apply_groupbox_surface
    gb = QGroupBox("probe")
    _apply_groupbox_surface(gb)
    assert gb.autoFillBackground() is True              # the lie
    assert gb.palette().color(QPalette.ColorRole.Window) == QColor(LM_BG_SURFACE)
    stop_lying()      # the app is really on DARK
    gb2 = QGroupBox("probe")
    _apply_groupbox_surface(gb2)
    assert gb2.autoFillBackground() is False


def test_5_icon_set_follows_the_answer(app, lying_theme):
    """The question this asks was renamed, and the rename is the point.

    It used to be `_is_light_palette()` — literally "is this the Light
    appearance". Both callers choose between two shipped ASSETS by whether the
    ground is pale, and a light-grey third appearance answers *no* to "are you
    Light" while needing every one of Light's files: light line art on a
    light-grey panel is an invisible folder button. It now asks
    `has_dark_ground`, which has a row per appearance.
    """
    stop_lying = lying_theme
    from ui.widgets import _has_light_ground
    assert _has_light_ground() is True                  # the lie
    stop_lying()      # the app is really on DARK
    assert _has_light_ground() is False


def test_6_check_refine_scanner_tip_follows_the_answer(app, lying_theme):
    stop_lying = lying_theme
    from ui.tabs.tab_check_refine import _scanner_tip_on_dark
    assert _scanner_tip_on_dark() is False              # the lie
    stop_lying()      # the app is really on DARK
    assert _scanner_tip_on_dark() is True


def test_7_scanner_target_row_follows_the_answer(app, lying_theme):
    stop_lying = lying_theme
    from PyQt6.QtWidgets import QLabel
    from ui.tabs.tab_measure import make_scanner_target_row
    parent = QWidget()
    row, _ = make_scanner_target_row(parent, False)
    styles = [lb.styleSheet() for lb in row.findChildren(QLabel) if lb.styleSheet()]
    assert any("#2f6b52" in st for st in styles)        # the lie: hint_light
    assert "0.10" in row.styleSheet()
    stop_lying()      # the app is really on DARK
    row2, _ = make_scanner_target_row(parent, False)
    styles2 = [lb.styleSheet() for lb in row2.findChildren(QLabel) if lb.styleSheet()]
    assert any("#a6e3ca" in st for st in styles2)
    assert "0.13" in row2.styleSheet()


# ------------------------------------------------------- no pixel left over

SEVEN_FILES = (
    "ui/bar_icons.py",
    "ui/cr30_pictograms.py",
    "ui/scan_grid_marquee.py",
    "ui/widgets.py",
    "ui/tabs/tab_check_refine.py",
    "ui/tabs/tab_measure.py",
)


def test_none_of_the_seven_modules_decides_a_theme_by_lightness():
    """A ``.lightness()`` compared against a constant is the shape of the bug.

    Only ``ui/theme.py`` is allowed one, and only in its unrecognised-palette
    fallback.
    """
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    pattern = re.compile(r"lightness\(\)\s*[<>]")
    offenders = []
    for rel in SEVEN_FILES:
        for n, line in enumerate(( root / rel).read_text().splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{rel}:{n}: {line.strip()}")
    assert not offenders, "theme decided by measuring a pixel:\n" + "\n".join(offenders)
