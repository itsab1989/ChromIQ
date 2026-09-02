"""The ICONS, in the Neutral appearance.

The owner, on the shipped build:

    "in general some icons still have colors"

and then, naming them:

    "tools icon, open project, open chart, close project icon still colored"
    "the agent working on the icons should make the outline of the tools icon
    darker"

Four kinds of icon were still carrying a hue, and each is pinned here:

1. **Baked-hue SVG assets** — the four masthead marks, whose colours live in a
   file rather than in code. :mod:`ui.icon_ink` substitutes the palette in the
   SVG source before Qt rasterises it.
2. **Painted glyph buttons** — the six marks in :mod:`ui.widgets` that took a
   spectrum accent at construction and declared ``set_appearance`` a no-op.
3. **Icon pixmaps built once** — the Profile-run bar's three marks, and the
   CR30 pictograms, both of which folded three appearances into two answers.
4. **Decoration that reads as an icon** — the five-cell rule under each tab's
   headline card, and the coloured mark the headline ends in.

**THE APPEARANCE IS SET BY PALETTE ONLY.** ``apply_appearance`` sets an app-wide
stylesheet, which re-polishes every live widget and has crashed an xdist worker
when a theme suite shared a process; ``active_mode()`` reads the palette, which
is all these resolvers need.

**LIGHT AND DARK MUST NOT MOVE.** Every fix here goes through ``accent_for`` /
``by_mode`` / :func:`ui.icon_ink.svg_renderer`, all of which are identity
outside Neutral, and several tests below assert that by rendering the same
widget in Light and Dark and comparing the bytes.
"""
from __future__ import annotations

import inspect

import pytest
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QWidget

from core.resource_path import resource_path
from ui import bar_icons, cr30_pictograms, icon_ink
from ui import neutral_styles as nm
from ui import widgets as W
from ui.light_styles import make_light_palette
from ui.neutral_styles import make_neutral_palette
from ui.styles import (
    SPEC_AMBER, SPEC_CYAN, SPEC_GREEN, SPEC_MAGENTA, SPEC_VIOLET,
    make_dark_palette,
)
from ui.theme import (
    APPEARANCE_DARK, APPEARANCE_LIGHT, APPEARANCE_NEUTRAL, active_mode,
)

MODES = (APPEARANCE_LIGHT, APPEARANCE_DARK, APPEARANCE_NEUTRAL)
_PALETTES = {
    APPEARANCE_LIGHT: make_light_palette,
    APPEARANCE_DARK: make_dark_palette,
    APPEARANCE_NEUTRAL: make_neutral_palette,
}

#: The four marks whose colour is baked into a shipped file. The ``_light``
#: artwork is what a pale ground gets, and Neutral is a pale ground.
MASTHEAD_ASSETS = ("load_project_light", "load_ti2_light",
                   "close_project_light", "tools_v2_light")

#: The six painted glyph buttons and the accent each is built with in the app.
GLYPH_BUTTONS = (
    (W.PatchGridButton, SPEC_MAGENTA),
    (W.StackedPagesButton, SPEC_MAGENTA),
    (W.StripReadButton, SPEC_GREEN),
    (W.MeasuredChartButton, SPEC_CYAN),
    (W.RevealFolderButton, SPEC_AMBER),
    (W.ImageFileButton, SPEC_AMBER),
)


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def wearing(qapp):
    """Put an appearance's PALETTE on the app, and put the old one back."""
    original = qapp.palette()

    def _wear(mode: str):
        qapp.setPalette(_PALETTES[mode]())
        assert active_mode() == mode, "the palette did not identify as itself"
        return mode

    yield _wear
    qapp.setPalette(original)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def hued_pixels(pm, tolerance: int = 6) -> int:
    """How many opaque pixels of *pm* are not a grey.

    The same measure ``scripts/find_non_neutral_pixels.py`` applies to a live
    window, so a green test here and a clean census there mean the same thing.
    """
    img = pm.toImage() if isinstance(pm, QPixmap) else pm
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    n = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() < 8:
                continue
            if max(c.red(), c.green(), c.blue()) \
                    - min(c.red(), c.green(), c.blue()) > tolerance:
                n += 1
    return n


def render_asset(stem: str, mode: "str | None", size: int = 40) -> QPixmap:
    """One masthead asset through the loader the masthead uses."""
    path = resource_path(f"assets/{stem}.svg")
    renderer = icon_ink.svg_renderer(path, mode)
    assert renderer.isValid(), f"{stem}: renderer refused the document"
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    from PyQt6.QtCore import QRectF
    renderer.render(p, QRectF(0, 0, size, size))
    p.end()
    return pm


def raw_render(stem: str, size: int = 40) -> QPixmap:
    """The same asset through a plain ``QSvgRenderer`` — what shipped."""
    from PyQt6.QtCore import QRectF
    renderer = QSvgRenderer(str(resource_path(f"assets/{stem}.svg")))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(p, QRectF(0, 0, size, size))
    p.end()
    return pm


def image_bytes(pm: QPixmap) -> bytes:
    img = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    return bytes(ptr)


def button_pixels(cls, colour: str, *, mode: "str | None" = None) -> QPixmap:
    btn = cls(colour)
    if mode is not None:
        btn.set_appearance(mode)
    btn.resize(40, 40)
    return btn.grab()


# ----------------------------------------------------------------------
# 1. the baked-hue SVG assets
# ----------------------------------------------------------------------
def test_1_the_shipped_assets_really_do_carry_a_hue():
    """The premise. If these ever stop being coloured files, the tests below
    would pass while proving nothing."""
    for stem in MASTHEAD_ASSETS:
        text = resource_path(f"assets/{stem}.svg").read_text(encoding="utf-8")
        hues = [h for h in icon_ink._HEX.findall(text)
                if _spread(h) > 6]
        assert hues, f"{stem}.svg no longer bakes a hue — retarget this suite"


def _spread(hexval: str) -> int:
    c = QColor(hexval)
    return max(c.red(), c.green(), c.blue()) - min(c.red(), c.green(), c.blue())


def test_1_neutral_colour_keeps_paper_and_inks_everything_else():
    assert icon_ink.neutral_colour("#fafafa") == "#fafafa"     # the page
    assert icon_ink.neutral_colour("#ffffff") == "#ffffff"     # the knockout
    for ink in ("#ff3a6b", "#ffb020", "#2bb8d4", "#c8c4be", "#2b2b2b"):
        assert icon_ink.neutral_colour(ink) == nm.NM_ACTION, ink


def test_1_the_tools_outline_goes_all_the_way_to_action():
    """The owner's second report, pinned to the value he was shown.

    ``#c8c4be`` is the toolbox's outline, and the toolbox is nothing but its
    outline. A merely-darker grey left it lighter than the settings sliders and
    the "?" beside it, both of which are ACTION.
    """
    assert icon_ink.neutral_colour("#c8c4be") == nm.NM_ACTION
    assert nm.NM_ACTION == "#101010", (
        "ACTION moved; the toolbox outline follows it and this test's premise "
        "needs re-reading, not re-baselining")


def test_1_neutral_svg_leaves_non_colour_values_alone():
    src = '<path fill="none" stroke="currentColor" d="M0 0h4"/>'
    assert icon_ink.neutral_svg(src) == src


@pytest.mark.parametrize("stem", MASTHEAD_ASSETS)
def test_1_asset_has_no_hue_left_in_neutral(qapp, stem):
    assert hued_pixels(render_asset(stem, APPEARANCE_NEUTRAL)) == 0


@pytest.mark.parametrize("stem", MASTHEAD_ASSETS)
@pytest.mark.parametrize("mode", (APPEARANCE_LIGHT, APPEARANCE_DARK))
def test_1_asset_is_byte_identical_outside_neutral(qapp, stem, mode):
    """The whole shape of the fix: Light and Dark get the file as drawn."""
    assert image_bytes(render_asset(stem, mode)) == image_bytes(raw_render(stem))


def test_1_asset_still_carries_a_hue_in_light(qapp):
    """A mutation that landed. Without it, "no hue in Neutral" would also be
    satisfied by an artwork that never had one."""
    assert hued_pixels(render_asset("tools_v2_light", APPEARANCE_LIGHT)) > 100


def test_1_the_masthead_asks_icon_ink_for_its_renderer():
    """The mutation is proven to land IN THE METHOD, not in a same-named line
    elsewhere: an earlier proof on this branch's predecessor patched a
    homonym in a different method and reported a pass."""
    from ui.masthead_header import MastheadHeader
    for method in (MastheadHeader._load_masthead_left_icons,
                   MastheadHeader._load_tools_icon):
        src = inspect.getsource(method)
        assert "icon_ink.svg_renderer(path, self._mode)" in src, method.__name__
        assert "QSvgRenderer(str(path))" not in src, method.__name__


def test_1_svg_renderer_survives_a_missing_file(qapp):
    """A bad path must not raise: an icon in the wrong palette is a fault and
    no icon at all is a worse one."""
    r = icon_ink.svg_renderer("/nonexistent/nothing.svg", APPEARANCE_NEUTRAL)
    assert r is not None and not r.isValid()


# ----------------------------------------------------------------------
# 2. the six painted glyph buttons
# ----------------------------------------------------------------------
@pytest.mark.parametrize("cls,colour", GLYPH_BUTTONS,
                         ids=[c.__name__ for c, _ in GLYPH_BUTTONS])
def test_2_glyph_button_has_no_hue_in_neutral(qapp, wearing, cls, colour):
    wearing(APPEARANCE_NEUTRAL)
    assert hued_pixels(button_pixels(cls, colour)) == 0


@pytest.mark.parametrize("cls,colour", GLYPH_BUTTONS,
                         ids=[c.__name__ for c, _ in GLYPH_BUTTONS])
def test_2_glyph_button_keeps_its_hue_in_light(qapp, wearing, cls, colour):
    """The mutation, proven to land: the same button in Light still paints the
    tab's accent, so the Neutral assertion above is measuring the resolver and
    not an empty widget."""
    wearing(APPEARANCE_LIGHT)
    assert hued_pixels(button_pixels(cls, colour)) > 50


@pytest.mark.parametrize("cls,colour", GLYPH_BUTTONS,
                         ids=[c.__name__ for c, _ in GLYPH_BUTTONS])
def test_2_a_live_switch_reaches_the_glyph(qapp, wearing, cls, colour):
    """Preferences switches appearance without a restart. A button built in
    Light and then TOLD it is in Neutral must repaint — this is what the six
    no-op ``set_appearance`` implementations did not do."""
    wearing(APPEARANCE_LIGHT)
    btn = cls(colour)
    btn.resize(40, 40)
    assert hued_pixels(btn.grab()) > 50
    btn.set_appearance(APPEARANCE_NEUTRAL)
    assert hued_pixels(btn.grab()) == 0
    btn.set_appearance(APPEARANCE_LIGHT)
    assert hued_pixels(btn.grab()) > 50


def test_2_no_glyph_button_declares_set_appearance_a_no_op():
    """The comment that was true for two appearances and wrong for three."""
    for cls, _ in GLYPH_BUTTONS:
        src = inspect.getsource(cls)
        assert "theme-independent" not in src, cls.__name__
        assert "self._glyph_colour()" in src, cls.__name__


def test_2_an_unknown_appearance_falls_back_to_the_live_palette(qapp, wearing):
    wearing(APPEARANCE_NEUTRAL)
    btn = W.PatchGridButton(SPEC_MAGENTA)
    btn.set_appearance("chartreuse")
    assert btn._mode is None
    btn.resize(40, 40)
    assert hued_pixels(btn.grab()) == 0


# ----------------------------------------------------------------------
# 3. the Profile-run bar, and the CR30 pictograms
# ----------------------------------------------------------------------
def test_3_bar_icon_drops_its_hue_in_neutral(qapp, wearing):
    wearing(APPEARANCE_NEUTRAL)
    btn = bar_icons.BarIconButton(bar_icons.draw_duplicate_run,
                                  SPEC_MAGENTA, "Duplicate")
    pm = btn.icon().pixmap(QSize(34, 34))
    assert hued_pixels(pm) == 0


def test_3_bar_icon_keeps_its_hue_in_light(qapp, wearing):
    wearing(APPEARANCE_LIGHT)
    btn = bar_icons.BarIconButton(bar_icons.draw_duplicate_run,
                                  SPEC_MAGENTA, "Duplicate")
    assert hued_pixels(btn.icon().pixmap(QSize(34, 34))) > 20


def test_3_the_disabled_grey_has_three_answers(qapp, wearing):
    """It had two, and Neutral was handed the LIGHT theme's grey — `#a8a4a0`,
    eight points of red over blue, which is a warm tint in a theme that has
    none."""
    seen = {}
    for mode in MODES:
        wearing(mode)
        # Built AFTER the palette is on the app. A widget that has never been
        # parented or shown does not pick up a later `QApplication.setPalette`,
        # and `_disabled_colour` reads the widget's own palette on purpose --
        # that is the one that has already changed inside a PaletteChange.
        btn = bar_icons.BarIconButton(bar_icons.draw_duplicate_run,
                                      SPEC_MAGENTA, "Duplicate")
        seen[mode] = btn._disabled_colour()
    assert seen[APPEARANCE_LIGHT] == bar_icons.BarIconButton.GREY_ON_LIGHT
    assert seen[APPEARANCE_DARK] == bar_icons.BarIconButton.GREY_ON_DARK
    assert seen[APPEARANCE_NEUTRAL] == nm.NM_DISABLED
    assert _spread(seen[APPEARANCE_NEUTRAL]) == 0


def test_3_a_theme_switch_restamps_the_bar_icon(qapp, wearing):
    """The bar's marks are pixmaps built once. A ``PaletteChange`` is how the
    switch reaches them, and it must re-run BOTH colours."""
    wearing(APPEARANCE_LIGHT)
    btn = bar_icons.BarIconButton(bar_icons.draw_duplicate_run,
                                  SPEC_MAGENTA, "Duplicate")
    assert hued_pixels(btn.icon().pixmap(QSize(34, 34))) > 20
    wearing(APPEARANCE_NEUTRAL)
    btn.setPalette(make_neutral_palette())
    btn._apply_icon()
    assert hued_pixels(btn.icon().pixmap(QSize(34, 34))) == 0


def test_3_cr30_pictogram_accent_has_three_answers(qapp, wearing):
    wearing(APPEARANCE_LIGHT)
    light = cr30_pictograms._accent(None)
    wearing(APPEARANCE_DARK)
    dark = cr30_pictograms._accent(None)
    wearing(APPEARANCE_NEUTRAL)
    neutral = cr30_pictograms._accent(None)
    assert light.name() == cr30_pictograms.ACCENT_LIGHT
    assert dark.name() == cr30_pictograms.ACCENT_DARK
    assert neutral.name() == nm.NM_ACTION


# ----------------------------------------------------------------------
# 4. the decoration that reads as an icon
# ----------------------------------------------------------------------
def test_4_spectrum_cell_collapses_to_one_accent(qapp, wearing):
    wearing(APPEARANCE_NEUTRAL)
    parent = QWidget()
    for hue in (SPEC_MAGENTA, SPEC_AMBER, SPEC_GREEN, SPEC_CYAN, SPEC_VIOLET):
        seg = W.spectrum_cell(parent, hue)
        assert nm.NM_ACTION in seg.styleSheet(), hue
        assert hue not in seg.styleSheet(), hue


def test_4_spectrum_cell_is_untouched_in_light_and_dark(qapp, wearing):
    parent = QWidget()
    for mode in (APPEARANCE_LIGHT, APPEARANCE_DARK):
        wearing(mode)
        assert SPEC_AMBER in W.spectrum_cell(parent, SPEC_AMBER).styleSheet()


def test_4_a_live_switch_reaches_every_cell(qapp, wearing):
    """There is no per-tab ``set_appearance`` for these, so the app-wide icon
    walker is what has to find them."""
    wearing(APPEARANCE_LIGHT)
    root = QWidget()
    cells = [W.spectrum_cell(root, h) for h in (SPEC_MAGENTA, SPEC_CYAN)]
    assert all(SPEC_MAGENTA in c.styleSheet() or SPEC_CYAN in c.styleSheet()
               for c in cells)
    wearing(APPEARANCE_NEUTRAL)
    W.apply_themed_icons(root)
    assert all(nm.NM_ACTION in c.styleSheet() for c in cells)
    wearing(APPEARANCE_LIGHT)
    W.apply_themed_icons(root)
    assert SPEC_MAGENTA in cells[0].styleSheet()
    assert SPEC_CYAN in cells[1].styleSheet()


def test_4_the_headline_mark_follows_the_appearance(qapp, wearing):
    tpl = ('Feed the beast<span style="color: {SPEC_AMBER}; '
           'font-style: italic;">!</span>')
    wearing(APPEARANCE_LIGHT)
    lbl = QLabel()
    W.set_accent_html(lbl, tpl, SPEC_AMBER=SPEC_AMBER)
    assert SPEC_AMBER in lbl.text()
    wearing(APPEARANCE_NEUTRAL)
    W.reapply_accent_html(lbl)
    assert nm.NM_ACTION in lbl.text() and SPEC_AMBER not in lbl.text()
    wearing(APPEARANCE_LIGHT)
    W.reapply_accent_html(lbl)
    assert SPEC_AMBER in lbl.text()


def test_4_the_headline_keeps_its_translated_template(qapp, wearing):
    """The re-fill must not re-fetch the translation: a label re-resolved after
    a language change would otherwise silently revert to English."""
    wearing(APPEARANCE_LIGHT)
    lbl = QLabel()
    W.set_accent_html(lbl, "Fütter das Biest<span "
                           'style="color: {X};">!</span>', X=SPEC_AMBER)
    wearing(APPEARANCE_NEUTRAL)
    W.reapply_accent_html(lbl)
    assert "Fütter das Biest" in lbl.text()


def test_4_the_walker_reaches_labels_and_cells_together(qapp, wearing):
    wearing(APPEARANCE_LIGHT)
    root = QWidget()
    cell = W.spectrum_cell(root, SPEC_VIOLET)
    lbl = QLabel(root)
    W.set_accent_html(lbl, 'x<span style="color: {C};">?</span>', C=SPEC_VIOLET)
    wearing(APPEARANCE_NEUTRAL)
    W.apply_themed_icons(root)
    assert nm.NM_ACTION in cell.styleSheet()
    assert nm.NM_ACTION in lbl.text()


def test_4_the_walker_ignores_an_untagged_frame(qapp, wearing):
    """A plain QFrame is not a spectrum cell and must be left alone."""
    wearing(APPEARANCE_NEUTRAL)
    root = QWidget()
    plain = QFrame(root)
    plain.setStyleSheet("background-color: #ff4573;")
    W.apply_themed_icons(root)
    assert plain.styleSheet() == "background-color: #ff4573;"


def test_4_every_tab_card_builds_its_rule_through_the_helper():
    """The mutation, proven to land in the five files it was meant for."""
    import ui.dialogs.ti2_relayout_dialog as relayout
    import ui.tabs.tab_check_refine as check
    import ui.tabs.tab_measure as measure
    import ui.tabs.tab_print as printtab
    import ui.tabs.tab_profile as profile
    for mod in (printtab, measure, profile, check, relayout):
        src = inspect.getsource(mod)
        assert "spectrum_cell(" in src, mod.__name__
        assert "_seg.setFixedSize(22, 2)" not in src, mod.__name__
        assert "seg.setFixedSize(22, 2)" not in src, mod.__name__
