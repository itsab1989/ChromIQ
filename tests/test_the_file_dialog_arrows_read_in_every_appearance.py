"""The file dialog's back / forward / up arrows must be VISIBLE in all three
appearances.

They were not. `ui/widgets._style_file_dialog_toolbar` chose the arrow colour
with a two-answer fold::

    mode = resolve_mode(AppSettings().get("appearance", "auto"))
    arrow_color = QColor("#1C1B18" if mode == APPEARANCE_LIGHT else "#e0e0e0")

Neutral is not Light, so it took the *dark* branch: `#e0e0e0` arrows on
Neutral's `#e2e2e2` toolbar. Measured on screen, all three buttons, every
state — normal **1.03:1**, hover 1.14:1, pressed 1.18:1, disabled 1.02:1.
Three ghosts where the navigation should be (Basti, 2026-09-05).

That is the exact fold `ui.theme.by_mode` exists to replace, and the same shape
CLAUDE.md records costing an appearance its assets elsewhere. The fix does not
add a third literal; it stops choosing a literal at all and reads the dialog's
own `ButtonText`, which every appearance already sets to the ink it wants on
its own buttons. So these tests pin the PROPERTY (the arrows clear AA on the
ground they sit on, in every appearance) rather than three hex values, and a
fourth appearance is covered the day its palette exists.
"""
import ast
import inspect
import textwrap

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtGui import QColor, QPalette                     # noqa: E402
from PyQt6.QtWidgets import (QApplication, QFileDialog,      # noqa: E402
                             QToolButton)

import ui.widgets as widgets                                 # noqa: E402
from ui.light_styles import make_light_palette               # noqa: E402
from ui.neutral_styles import make_neutral_palette           # noqa: E402
from ui.styles import make_dark_palette                      # noqa: E402

#: WCAG 2.1 AA for text. Icons are not text, but these arrows ARE the only
#: label those buttons carry, so the app's text bar is the one to hold them to.
AA = 4.5

_PALETTES = {
    "light":   make_light_palette,
    "dark":    make_dark_palette,
    "neutral": make_neutral_palette,
}

#: The four helpers in `ui/widgets.py` that open a file dialog. Every one of
#: them must style its toolbar, or "fixed for all such dialogs" is not true.
_DIALOG_HELPERS = ("open_file_dialog", "open_files_dialog",
                   "save_file_dialog", "open_dir_dialog")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _relative_luminance(c: QColor) -> float:
    def channel(v: float) -> float:
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (0.2126 * channel(c.red())
            + 0.7152 * channel(c.green())
            + 0.0722 * channel(c.blue()))


def contrast_ratio(a: QColor, b: QColor) -> float:
    """WCAG 2.1 contrast ratio between two opaque colours."""
    la, lb = _relative_luminance(a), _relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _dialog(qapp, palette: QPalette) -> QFileDialog:
    """A real non-native QFileDialog wearing `palette`, styled by the shipped
    `_style_file_dialog_toolbar` — the same two lines, in the same order, that
    all four helpers in `ui/widgets.py` run."""
    dlg = QFileDialog(None, "nav arrows", str(widgets.Path.home()))
    dlg.setOption(QFileDialog.Option.DontUseNativeDialog)
    dlg.setPalette(palette)
    widgets._style_file_dialog_toolbar(dlg)
    return dlg


def _painted_arrow_ink(btn) -> "QColor | None":
    """The colour the button's icon actually paints its arrow in — the
    commonest fully-opaque colour in the rendered icon. `_nav_icon` centres a
    16x16 glyph on a transparent 28x28 canvas and fills it SourceIn, so the
    opaque pixels ARE the arrow, and there is one of them by colour."""
    image = btn.icon().pixmap(widgets._NAV_BTN_SIZE).toImage()
    counts: "dict[int, int]" = {}
    for y in range(image.height()):
        for x in range(image.width()):
            c = image.pixelColor(x, y)
            if c.alpha() > 200:
                counts[c.rgb()] = counts.get(c.rgb(), 0) + 1
    if not counts:
        return None
    return QColor.fromRgb(max(counts, key=counts.get))


def _function_body_source(func) -> str:
    """The function's source with its docstring removed — so a docstring that
    QUOTES the old broken line cannot satisfy or trip a source-level guard."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    fn = tree.body[0]
    body = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr)
                           and isinstance(fn.body[0].value, ast.Constant)
                           and isinstance(fn.body[0].value.value, str)
                           ) else fn.body
    return "\n".join(ast.unparse(node) for node in body)


def test_every_file_dialog_helper_styles_its_toolbar():
    """One fix has to reach every dialog, so every helper must go through the
    one function. A helper that forgets is a dialog that keeps the bug."""
    for name in _DIALOG_HELPERS:
        src = inspect.getsource(getattr(widgets, name))
        assert "_style_file_dialog_toolbar(dlg)" in src, (
            f"ui.widgets.{name} does not style its toolbar — its back/forward/"
            "up arrows are whatever the platform style paints")


@pytest.mark.parametrize("appearance", sorted(_PALETTES))
def test_the_nav_arrow_ink_is_the_dialogs_own_button_text(qapp, appearance):
    """The colour is READ from the palette, never picked per appearance."""
    palette = _PALETTES[appearance]()
    dlg = _dialog(qapp, palette)
    try:
        assert widgets.nav_arrow_ink(dlg) == palette.color(
            QPalette.ColorGroup.Active, QPalette.ColorRole.ButtonText)
    finally:
        dlg.deleteLater()


@pytest.mark.parametrize("appearance", sorted(_PALETTES))
def test_the_nav_arrows_clear_wcag_aa_on_every_appearances_toolbar(
        qapp, appearance):
    """The property that broke, measured on the PIXELS the buttons carry.

    Not on what `nav_arrow_ink` returns — a colour the icon never receives
    fixes nothing, and an earlier draft of this test proved exactly that by
    staying green while the old fold was put back. The ink is read out of the
    rendered icon, and held against the two grounds a nav button sits on: the
    dialog's Window (the toolbar strip) and the Button role (the fill a
    hovered or pressed nav button takes).

    Before the fix Neutral scored **1.03:1** here."""
    palette = _PALETTES[appearance]()
    dlg = _dialog(qapp, palette)
    try:
        for name in widgets._NAV_BUTTONS:
            btn = dlg.findChild(QToolButton, name)
            assert btn is not None, f"{name} is missing from the file dialog"
            ink = _painted_arrow_ink(btn)
            assert ink is not None, f"{appearance}/{name}: icon paints nothing"
            for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Button):
                ground = palette.color(QPalette.ColorGroup.Active, role)
                ratio = contrast_ratio(ink, ground)
                assert ratio >= AA, (
                    f"{appearance}/{name}: arrow {ink.name()} on {role.name} "
                    f"{ground.name()} is {ratio:.2f}:1, under AA {AA}:1")
    finally:
        dlg.deleteLater()


@pytest.mark.parametrize("appearance", sorted(_PALETTES))
def test_the_nav_arrow_icon_is_actually_painted_in_that_ink(qapp, appearance):
    """The ink the palette gives has to be the ink on the glyph.

    The SourceIn fill in `_nav_icon` makes the solid part of the arrow exactly
    that colour, so the two can simply be compared."""
    palette = _PALETTES[appearance]()
    dlg = _dialog(qapp, palette)
    try:
        ink = widgets.nav_arrow_ink(dlg)
        for name in widgets._NAV_BUTTONS:
            btn = dlg.findChild(QToolButton, name)
            assert btn is not None, f"{name} is missing from the file dialog"
            painted = _painted_arrow_ink(btn)
            assert painted is not None and painted.rgb() == ink.rgb(), (
                f"{appearance}/{name}: the arrow is painted "
                f"{painted.name() if painted else 'nothing'}, "
                f"but the palette ink is {ink.name()}")
    finally:
        dlg.deleteLater()


def test_the_arrow_colour_is_not_chosen_by_a_two_answer_appearance_fold():
    """The shape of the bug, not just this instance of it.

    `X if mode == "light" else Y` has room for two answers and files every
    other appearance under the second one. Neither the styling function nor
    the ink function may name an appearance or spell a colour."""
    for func in (widgets._style_file_dialog_toolbar, widgets.nav_arrow_ink):
        body = _function_body_source(func)
        assert "APPEARANCE_" not in body, (
            f"{func.__name__} branches on an appearance name again — that is "
            "the fold that left Neutral with 1.03:1 arrows")
        assert "resolve_mode" not in body, (
            f"{func.__name__} resolves the appearance itself again")
        assert "#" not in body, (
            f"{func.__name__} spells a colour literal — the ink must come "
            "from the palette, so a new appearance needs no edit here")
    assert "ButtonText" in _function_body_source(widgets.nav_arrow_ink), (
        "nav_arrow_ink no longer reads the palette's ButtonText role")
