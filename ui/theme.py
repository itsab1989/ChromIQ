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
from ui import light_styles, neutral_styles, styles
from ui.light_styles import LIGHT_STYLESHEET, make_light_palette
from ui.neutral_styles import NEUTRAL_STYLESHEET, make_neutral_palette
from ui.styles import APP_STYLESHEET, make_dark_palette

if TYPE_CHECKING:
    from ui.main_window import MainWindow

log = get_logger(__name__)

APPEARANCE_LIGHT   = "light"
APPEARANCE_DARK    = "dark"
#: The third appearance: a light-grey working environment with no colour
#: anywhere in the interface. Its values live in :mod:`ui.neutral_styles`.
APPEARANCE_NEUTRAL = "neutral"
APPEARANCE_AUTO    = "auto"

VALID_APPEARANCES = (APPEARANCE_LIGHT, APPEARANCE_DARK, APPEARANCE_NEUTRAL,
                     APPEARANCE_AUTO)

#: The concrete appearances — the answers :func:`active_mode` can give. AUTO is
#: not here: it is a *setting*, and resolves to one of these.
#:
#: NEUTRAL is not something AUTO can resolve to: the OS reports light or dark
#: and has no third scheme to follow, so Neutral is only ever reached by asking
#: for it by name.
CONCRETE_APPEARANCES = (APPEARANCE_LIGHT, APPEARANCE_DARK, APPEARANCE_NEUTRAL)

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
    # THE ROW THIS TABLE WAS BUILT FOR. Neutral's window is L* 90 and its
    # panel L* 93: every lightness threshold the app ever used (127, 128, 150)
    # calls that "light". Only an identification tells the two apart, and this
    # is it.
    APPEARANCE_NEUTRAL: {
        QPalette.ColorRole.Window:     neutral_styles.NM_BG_WINDOW,
        QPalette.ColorRole.WindowText: neutral_styles.NM_TEXT_MAIN,
    },
}

#: The role order :func:`active_mode` consults. Window first: it is what the
#: sites that ask this question have always read, and it is the one the two
#: appearances differ in most.
_FINGERPRINT_ROLES = (QPalette.ColorRole.Window, QPalette.ColorRole.WindowText)


#: Whether each concrete appearance paints a DARK ground. DECLARED, not
#: measured — the same principle as :data:`_FINGERPRINTS`, and it needs the
#: same one-line edit per appearance.
#:
#: A handful of sites genuinely have only two answers to give, because
#: something outside ChromIQ offers only two: macOS's native title bar has
#: ``NSAppearanceNameAqua`` and ``NSAppearanceNameDarkAqua`` and no third.
#: Those sites ask :func:`has_dark_ground` — which KIND of appearance is this —
#: instead of testing the name against ``"light"``, which a light-grey third
#: appearance would fail while needing the light answer.
_DARK_GROUND: "dict[str, bool]" = {
    APPEARANCE_LIGHT:   False,
    APPEARANCE_DARK:    True,
    # Light-grey, so the light answer — this is the row that keeps a black
    # native title bar off a light-grey window.
    APPEARANCE_NEUTRAL: False,
}


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


def accept_mode(mode: str, default: str = APPEARANCE_DARK) -> str:
    """Keep the appearance a component was handed — whole.

    THE ONE PLACE A BROADCAST APPEARANCE IS ADMITTED. Sixteen components used
    to open with ``self._mode = "light" if mode == "light" else "dark"``. That
    reads like validation and is not: it is a *fold*. It has room for two
    answers and quietly files everything else under Dark, so an appearance
    :func:`apply_appearance` broadcast correctly to all twenty-one
    ``set_appearance`` implementations would have been thrown away by sixteen
    of them — a light-grey window with a dark masthead, a dark tab bar, a dark
    tool popup and a dark TIFF preview.

    The defensive purpose is kept and the ceiling is not: any appearance listed
    in :data:`CONCRETE_APPEARANCES` survives, anything else becomes ``default``.
    **Adding a third appearance is adding it to that tuple** — the same shape
    as adding a row to :data:`_FINGERPRINTS`, and nothing downstream of the
    door needs to learn its name to carry it.

    With today's two appearances this is exactly what the fold did:
    ``'light'`` → ``'light'``, ``'dark'`` → ``'dark'``, and anything else
    (``'auto'``, ``''``, ``None``, a typo) → ``'dark'``.

    This says nothing about what a component should then PAINT. A component
    that still picks its colours with ``X if self._mode == "light" else Y``
    will paint a third appearance in Y — but it now knows which appearance it
    is in, which is the difference between a value that can be added and one
    that was destroyed on arrival.
    """
    return mode if mode in CONCRETE_APPEARANCES else default


def has_dark_ground(mode: str) -> bool:
    """Does this named appearance paint a dark ground?

    For the few sites whose answer really is binary because something outside
    ChromIQ offers only two — see :data:`_DARK_GROUND`. Such a site must not
    ask ``mode == "light"``: a light-grey third appearance is not called
    "light", would take the dark branch, and would put a black native title bar
    over a light-grey window.

    Takes a mode NAME, not a palette: the caller already has the appearance it
    was handed, and may be acting on it before it is on screen.
    :func:`is_dark` is the palette-side sibling.

    An appearance not in the table is treated as dark — the historical default,
    and what every caller did with an unrecognised value before.
    """
    return _DARK_GROUND.get(mode, True)


def resolve_mode(setting: str) -> str:
    """Return the concrete appearance for the given setting value.

    A setting that already names one of :data:`CONCRETE_APPEARANCES` — light,
    dark or neutral — passes straight through. Auto consults Qt's
    QStyleHints.colorScheme(), which reports light or dark and knows nothing of
    a third scheme, so Auto never resolves to Neutral. If the platform reports
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


#: ``{mode: (stylesheet, palette factory)}`` — what each concrete appearance
#: PAINTS. A table rather than ``LIGHT_STYLESHEET if mode == "light" else
#: APP_STYLESHEET``, for the same reason :data:`_FINGERPRINTS` is a table: that
#: expression had room for two answers and gave the dark sheet to everything
#: else, so a third appearance would have arrived as a light-grey palette
#: wearing the dark stylesheet. Adding an appearance is adding a row.
_APPEARANCE_STYLE: "dict[str, tuple[str, object]]" = {
    APPEARANCE_LIGHT:   (LIGHT_STYLESHEET,   make_light_palette),
    APPEARANCE_DARK:    (APP_STYLESHEET,     make_dark_palette),
    APPEARANCE_NEUTRAL: (NEUTRAL_STYLESHEET, make_neutral_palette),
}


def apply_appearance(
    app: QApplication,
    main_window: "MainWindow | None",
    setting: str,
) -> str:
    """Apply palette + stylesheet for `setting`.

    `setting` is one of :data:`VALID_APPEARANCES` — 'light', 'dark', 'neutral'
    or 'auto'. Returns the resolved concrete mode, one of
    :data:`CONCRETE_APPEARANCES`. Safe to call multiple times.
    """
    if setting not in VALID_APPEARANCES:
        log.warning("Unknown appearance %r — falling back to auto", setting)
        setting = APPEARANCE_AUTO
    mode = resolve_mode(setting)
    try:
        stylesheet, make_palette = _APPEARANCE_STYLE[mode]
    except KeyError:
        # A concrete appearance with no row here paints nothing of its own.
        # Loud, not silent: a quiet fall-through to Dark is precisely the fold
        # this table replaced. `tests/test_neutral_appearance.py` fails first.
        log.error("No style registered for appearance %r — using dark", mode)
        stylesheet, make_palette = _APPEARANCE_STYLE[APPEARANCE_DARK]
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
        app.setPalette(make_palette())
        app.setStyleSheet(stylesheet)
    if main_window is not None and hasattr(main_window, "apply_theme"):
        main_window.apply_theme(mode)
    log.debug("Appearance applied: setting=%s mode=%s", setting, mode)
    return mode
