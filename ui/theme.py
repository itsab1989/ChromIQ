"""Central appearance applier.

Single entry point for switching the app between Light, Dark, and Auto
(follows the system) themes. Selects the right QPalette + QSS for the app,
and asks the MainWindow to update its masthead and native title-bar.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from core.logger import get_logger
from ui.light_styles import LIGHT_STYLESHEET, make_light_palette
from ui.styles import APP_STYLESHEET, make_dark_palette

if TYPE_CHECKING:
    from ui.main_window import MainWindow

log = get_logger(__name__)

APPEARANCE_LIGHT = "light"
APPEARANCE_DARK  = "dark"
APPEARANCE_AUTO  = "auto"

VALID_APPEARANCES = (APPEARANCE_LIGHT, APPEARANCE_DARK, APPEARANCE_AUTO)


def resolve_mode(setting: str) -> str:
    """Return 'light' or 'dark' for the given setting value.

    Auto consults Qt's QStyleHints.colorScheme(). If the platform reports
    Unknown, fall back to 'dark' (the historical default).
    """
    if setting == APPEARANCE_LIGHT:
        return APPEARANCE_LIGHT
    if setting == APPEARANCE_DARK:
        return APPEARANCE_DARK
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
