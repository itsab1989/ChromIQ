"""Central appearance applier.

Single entry point for switching the app between Light, Dark, and Auto
(follows the system) themes. Selects the right QPalette + QSS for the app,
and asks the MainWindow to update its masthead and native title-bar.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

from core.logger import get_logger
from ui import light_styles, styles
from ui.light_styles import LIGHT_STYLESHEET, make_light_palette
from ui.styles import APP_STYLESHEET, make_dark_palette

if TYPE_CHECKING:
    from ui.main_window import MainWindow

log = get_logger(__name__)

APPEARANCE_LIGHT = "light"
APPEARANCE_DARK  = "dark"
APPEARANCE_AUTO  = "auto"

VALID_APPEARANCES = (APPEARANCE_LIGHT, APPEARANCE_DARK, APPEARANCE_AUTO)

#: The concrete appearances — the answers :func:`active_mode` can give. AUTO is
#: not here: it is a *setting*, and resolves to one of these.
CONCRETE_APPEARANCES = (APPEARANCE_LIGHT, APPEARANCE_DARK)

#: How an appearance is RECOGNISED on screen, rather than guessed at.
#:
#: Each entry is the set of palette colours that appearance paints and no other
#: does — its fingerprint. :func:`active_mode` looks the live palette up in
#: here, so the answer is an identification, not a measurement of how light a
#: pixel happens to be.
#:
#: Two roles, in this order, because one of them can legitimately be overridden
#: under us: ``ui.widgets._apply_groupbox_surface`` repaints a QGroupBox's
#: Window role with the light theme's surface colour, so a widget *inside* a
#: group box inherits a Window colour that belongs to no appearance's
#: fingerprint. WindowText is never overridden that way and settles it.
#:
#: **Adding a third appearance is adding a row here.** Nothing else in the app
#: needs to learn about it, which is the whole point of this table: at L* 93 a
#: light-grey theme is indistinguishable from Light to any lightness threshold,
#: and identical to it to none of these fingerprints.
_FINGERPRINTS: "dict[str, dict[QPalette.ColorRole, str]]" = {
    APPEARANCE_LIGHT: {
        QPalette.ColorRole.Window:     light_styles.LM_BG_WINDOW,
        QPalette.ColorRole.WindowText: light_styles.LM_TEXT_MAIN,
    },
    APPEARANCE_DARK: {
        QPalette.ColorRole.Window:     styles.BG_PANEL,
        QPalette.ColorRole.WindowText: styles.TEXT_MAIN,
    },
}

#: The role order :func:`active_mode` consults. Window first: it is what the
#: sites that ask this question have always read, and it is the one the two
#: appearances differ in most.
_FINGERPRINT_ROLES = (QPalette.ColorRole.Window, QPalette.ColorRole.WindowText)


#: ``{role: {rgb: mode}}`` — :data:`_FINGERPRINTS` inverted for lookup. Built
#: once at import because the table is static; call
#: :func:`_rebuild_fingerprint_index` after adding a row to it.
_MODE_BY_RGB: "dict[QPalette.ColorRole, dict[int, str]]" = {}


def _rebuild_fingerprint_index() -> None:
    _MODE_BY_RGB.clear()
    for role in _FINGERPRINT_ROLES:
        _MODE_BY_RGB[role] = {QColor(hexes[role]).rgb(): mode
                              for mode, hexes in _FINGERPRINTS.items()}


_rebuild_fingerprint_index()

#: Only reached for a palette no ChromIQ appearance painted. 128 is the middle
#: of the three thresholds the seven sites used, and gives the same answer as
#: all three for every palette they were ever handed.
_UNRECOGNISED_MIDPOINT = 128


def active_mode(palette: "QPalette | None" = None) -> str:
    """Which appearance is on screen right now — 'light' or 'dark'.

    THE ONE PLACE THAT ANSWERS "WHICH THEME IS THIS?". Seven sites used to work
    it out for themselves by measuring how light a background was, against three
    different thresholds (127, 128, 150). That is not a question a pixel can
    answer: two appearances can share a lightness, and a light-grey third one
    would read as Light to every threshold in the app while needing none of
    Light's assets. So this identifies the palette instead of measuring it.

    ``palette`` defaults to the application palette, which is what
    :func:`apply_appearance` sets and therefore the app-wide answer. Pass a
    widget's own palette only where the question really is about that widget's
    ground.

    This deliberately reads the LIVE palette rather than the stored setting.
    Several callers run inside a ``PaletteChange`` event — the palette has
    already changed at that point, and the setting may not have been written
    yet (or at all: a preview, a dialog, a test that paints a palette directly).

    An unrecognised palette — one ChromIQ did not paint — falls back to the
    historical lightness rule so nothing that works today stops working. That
    branch cannot tell a third appearance from Light, which is exactly why
    every appearance the app ships must appear in :data:`_FINGERPRINTS`;
    ``tests/test_theme_is_asked_not_guessed.py`` fails if one does not.
    """
    if palette is None:
        app = QApplication.instance()
        if app is None:
            return APPEARANCE_DARK          # the historical default, unchanged
        palette = app.palette()
    for role in _FINGERPRINT_ROLES:
        mode = _MODE_BY_RGB[role].get(palette.color(role).rgb())
        if mode is not None:
            return mode
    # Not one of ours. Guess, and say so in the log — this is the only guess
    # left in the app and it should be loud enough to notice.
    window = palette.color(QPalette.ColorRole.Window)
    guess = (APPEARANCE_LIGHT if window.lightness() > _UNRECOGNISED_MIDPOINT
             else APPEARANCE_DARK)
    log.debug("active_mode: unrecognised palette (window=%s) — guessing %s",
              window.name(), guess)
    return guess


def is_dark(palette: "QPalette | None" = None) -> bool:
    """``active_mode(...) == 'dark'`` — for the sites that only need the flag.

    A named opposite of "light" rather than "not light": when a third
    appearance lands, ``not is_dark()`` and ``is_light()`` stop being the same
    question, and code that says which one it meant will not have to be read
    twice.
    """
    return active_mode(palette) == APPEARANCE_DARK


def is_light(palette: "QPalette | None" = None) -> bool:
    """``active_mode(...) == 'light'``. See :func:`is_dark`."""
    return active_mode(palette) == APPEARANCE_LIGHT


def resolve_mode(setting: str) -> str:
    """Return 'light' or 'dark' for the given setting value.

    Auto consults Qt's QStyleHints.colorScheme(). If the platform reports
    Unknown, fall back to 'dark' (the historical default).
    """
    if setting in CONCRETE_APPEARANCES:
        return setting          # already concrete — light, dark, or a future one
    app = QApplication.instance()
    if app is None:
        return APPEARANCE_DARK
    try:
        scheme = app.styleHints().colorScheme()
    except Exception:
        return APPEARANCE_DARK
    if scheme == Qt.ColorScheme.Light:
        return APPEARANCE_LIGHT
    return APPEARANCE_DARK


def apply_appearance(
    app: QApplication,
    main_window: "MainWindow | None",
    setting: str,
) -> str:
    """Apply palette + stylesheet for `setting` ('light' | 'dark' | 'auto').

    Returns the resolved concrete mode ('light' or 'dark').
    Safe to call multiple times.
    """
    if setting not in VALID_APPEARANCES:
        log.warning("Unknown appearance %r — falling back to auto", setting)
        setting = APPEARANCE_AUTO
    mode = resolve_mode(setting)
    stylesheet = LIGHT_STYLESHEET if mode == APPEARANCE_LIGHT else APP_STYLESHEET
    # Setting an app-wide stylesheet forces Qt to re-polish *every* existing
    # widget — ~2 s for our ~2500-widget tree on a cold start. At launch this
    # runs twice with the same resolved mode: once before the window exists (to
    # seed the QSS so widgets polish correctly as they are built) and once after
    # (to sync window-only chrome). The second call would re-polish the whole
    # tree against a stylesheet that is already in effect. Skip that redundant
    # re-polish when the QSS is unchanged; a genuine theme switch changes the
    # string and still applies in full. apply_theme() below always runs so the
    # window-only bits (macOS native title bar, masthead, per-tab accents) sync
    # regardless of whether the app-wide QSS was touched.
    if app.styleSheet() != stylesheet:
        app.setPalette(make_light_palette() if mode == APPEARANCE_LIGHT else make_dark_palette())
        app.setStyleSheet(stylesheet)
    if main_window is not None and hasattr(main_window, "apply_theme"):
        main_window.apply_theme(mode)
    log.debug("Appearance applied: setting=%s mode=%s", setting, mode)
    return mode
