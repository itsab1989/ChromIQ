"""Neutral — the viewers, and the frames around them.

Every view in ChromIQ that shows the user's own colour sits in a *well*: the
TIFF chart preview, the 3D gamut viewer, the soft-proof, the patch cube and the
scan-grid marquee. THE CONTENT OF THOSE VIEWS IS THE USER'S WORK AND KEEPS ITS
COLOUR. The well around it is chrome, and in Neutral it goes grey.

Before this, five of them asked ``"#efebe6" if mode == "light" else "#111111"``
and handed a light-grey theme the DARK answer — a black hole covering 27–40 %
of four tabs, at 15.84:1 against the panel. The appearance was arriving intact;
only the value was missing.

What is proved here:

* **the well is the panel grey.** ``BG_PANEL``, not the handoff's darker
  ``BG_VIEWER`` — the owner's instruction, in his words: *"the tiff preview
  should have the same background colours as the light grey used for the
  majority of the main window panel."* The same value in the gamut well, the
  soft-proof and the marquee, because those wells sit on the same screens;
* **the patch cube stays at ``BG_VIEWER``, and that is a decision, not an
  oversight** — its data includes white and near-white patches, which vanish on
  a panel-grey ground and survive on the viewer value;
* **every value these five files can reach in Neutral is a true neutral**
  (R = G = B), and no light constant from the dark theme is painted on a light
  ground;
* **the marquee's marching ants are ``ACTION`` with an under-stroke** — over a
  printed patch of any density, which is what Measure green did for free;
* **the chart and the gamut are not repainted by the theme.** The same TIFF and
  the same 3D scene, rendered in Dark and in Neutral, are identical everywhere
  they are not the ground.

APPEARANCE IS SET BY PALETTE AND PER-WIDGET STYLESHEET, NEVER BY
``apply_appearance`` — an app-wide ``setStyleSheet`` in a test re-polishes every
live widget and crashed an xdist worker (CLAUDE.md).
"""
from __future__ import annotations

import pytest
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

from ui import neutral_styles as N
from ui import gamut_panel as GP
from ui import patch_cube_panel as PCP
from ui import scan_grid_marquee as SGM
from ui import tiff_preview as TP
from ui.dialogs import softproof_dialog as SPD

LIGHT, DARK, NEUTRAL = "light", "dark", "neutral"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _is_neutral(value: str) -> bool:
    """A true neutral: R = G = B. ``rgba(...)`` forms are unpacked first."""
    v = value.strip()
    if v.startswith("rgba(") or v.startswith("rgb("):
        parts = [int(float(p)) for p in v[v.index("(") + 1:v.index(")")].split(",")]
        r, g, b = parts[:3]
    else:
        c = QColor(v)
        assert c.isValid(), value
        r, g, b = c.red(), c.green(), c.blue()
    return r == g == b


def _lum(value: str) -> float:
    c = QColor(value)
    parts = [x / 255 for x in (c.red(), c.green(), c.blue())]
    lin = [p / 12.92 if p <= 0.03928 else ((p + 0.055) / 1.055) ** 2.4
           for p in parts]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


# ======================================================================
# 1. The wells are the panel grey — the thing the owner asked for
# ======================================================================

WELLS = [
    ("tiff preview",   lambda: TP._PREVIEW_NEUTRAL["img_bg"]),
    ("gamut viewer",   lambda: GP._PALETTE_NEUTRAL["frame_bg"]),
    ("soft-proof",     lambda: SPD._PALETTE_NEUTRAL["bg"]),
    ("scan marquee",   lambda: SGM._BACKDROP_BY_MODE[NEUTRAL]),
]


@pytest.mark.parametrize("name,get", WELLS, ids=[w[0] for w in WELLS])
def test_the_well_is_the_panel_grey(name, get):
    """The owner's value, in his words: the same light grey as the panel."""
    assert get() == N.NM_BG_PANEL


@pytest.mark.parametrize("name,get", WELLS, ids=[w[0] for w in WELLS])
def test_the_well_is_no_longer_the_dark_theme_s_hole(name, get):
    """#111111 on a light-grey page is 15.84:1 — a hole, not a well."""
    assert get() != "#111111"
    assert _contrast(get(), N.NM_BG_PANEL) < 1.05


def test_the_patch_cube_keeps_the_darker_viewer_value_on_purpose():
    """THE ONE WELL THAT IS NOT THE PANEL GREY, AND THE REASON IT IS NOT.

    The cube's dots are the patch set's own colours, and a patch set contains
    white and near-white patches. On the panel a white dot is 1.30:1 against its
    ground; on BG_VIEWER it is 1.48:1 and survives better. This view exists to
    show *where the patches are*, so a patch that cannot be seen is data lost —
    which is why this one keeps a step down and the others do not.

    THE MARGIN NARROWED AND THE REASON DID NOT. The panel was #ebebeb, where a
    white dot reached 1.13:1; the owner collapsed the grounds onto #e2e2e2 on
    2026-09-02, which lifted that to 1.30:1 on its own. The well is still the
    darker of the two and still the better ground for a white dot, which is the
    whole claim — but it is no longer 20 % better, so the test asks for the
    ordering it actually depends on rather than a margin that has moved once.
    """
    assert PCP._THEME[NEUTRAL]["bg"] == N.NM_BG_VIEWER
    white_on_panel = _contrast("#ffffff", N.NM_BG_PANEL)
    white_on_well = _contrast("#ffffff", N.NM_BG_VIEWER)
    assert white_on_well > white_on_panel
    # …and the well is a real step down, not a rounding difference.
    assert QColor(N.NM_BG_VIEWER).lightness() + 8 < QColor(N.NM_BG_PANEL).lightness()


# ======================================================================
# 2. Everything these files can reach in Neutral is a true neutral
# ======================================================================

NEUTRAL_PALETTES = [
    ("tiff preview", lambda: TP._PREVIEW_NEUTRAL),
    ("gamut panel",  lambda: GP._PALETTE_NEUTRAL),
    ("soft-proof",   lambda: SPD._PALETTE_NEUTRAL),
    ("patch cube",   lambda: PCP._THEME[NEUTRAL]),
]


@pytest.mark.parametrize("name,get", NEUTRAL_PALETTES,
                         ids=[p[0] for p in NEUTRAL_PALETTES])
def test_no_hue_survives_in_the_frame(name, get):
    for key, value in get().items():
        assert _is_neutral(value), f"{name}.{key} = {value} is not a grey"


def test_the_marquee_paints_no_hue_in_neutral():
    for table in (SGM._ACCENT_BY_MODE, SGM._UNDER_BY_MODE, SGM._BACKDROP_BY_MODE,
                  SGM._EMPTY_TEXT_BY_MODE):
        value = table[NEUTRAL]
        assert value is None or _is_neutral(
            value.name() if isinstance(value, QColor) else value)


def test_the_tooltip_block_is_a_grey_card():
    """The preview's own QToolTip block, which the global rule cannot reach."""
    assert N.NM_BG_SURFACE in TP._TOOLTIP_QSS_NEUTRAL
    assert N.NM_TEXT_MAIN in TP._TOOLTIP_QSS_NEUTRAL
    assert TP._TOOLTIP_QSS_BY_MODE[NEUTRAL] is TP._TOOLTIP_QSS_NEUTRAL


# ======================================================================
# 3. Rule 2 — all text is dark; there is no inverted text anywhere
# ======================================================================

INK_ON_GROUND = [
    ("preview caption",    lambda: (TP._PREVIEW_NEUTRAL["caption"], N.NM_BG_WINDOW)),
    ("preview filename",   lambda: (TP._PREVIEW_NEUTRAL["filename"], N.NM_BG_WINDOW)),
    ("preview page",       lambda: (TP._PREVIEW_NEUTRAL["page"], N.NM_BG_WINDOW)),
    ("empty-state line",   lambda: (TP._PREVIEW_NEUTRAL["img_text"], N.NM_BG_PANEL)),
    ("ink readout",        lambda: (TP._PREVIEW_NEUTRAL["readout"], N.NM_BG_PANEL)),
    ("banner text",        lambda: (TP._PREVIEW_NEUTRAL["banner_text"],
                                    TP._PREVIEW_NEUTRAL["banner_bg"])),
    ("file tip",           lambda: (TP._PREVIEW_NEUTRAL["tip_text"],
                                    TP._PREVIEW_NEUTRAL["tip_bg"])),
    ("gamut header",       lambda: (GP._PALETTE_NEUTRAL["hdr"], N.NM_BG_WINDOW)),
    ("gamut profile line", lambda: (GP._PALETTE_NEUTRAL["profile"], N.NM_BG_PANEL)),
    ("gamut placeholder",  lambda: (GP._PALETTE_NEUTRAL["placeholder"], N.NM_BG_PANEL)),
    ("proof placeholder",  lambda: (SPD._PALETTE_NEUTRAL["placeholder"], N.NM_BG_PANEL)),
    ("proof toggle label", lambda: (SPD._PALETTE_NEUTRAL["toggle_fg"],
                                    SPD._PALETTE_NEUTRAL["toggle_bg"])),
    ("proof warning",      lambda: (SPD._PALETTE_NEUTRAL["warn_fg"],
                                    SPD._PALETTE_NEUTRAL["warn_bg"])),
    ("cube labels",        lambda: (PCP._THEME[NEUTRAL]["fg"],
                                    PCP._THEME[NEUTRAL]["bg"])),
    ("marquee empty line", lambda: (SGM._EMPTY_TEXT_BY_MODE[NEUTRAL],
                                    SGM._BACKDROP_BY_MODE[NEUTRAL])),
]


@pytest.mark.parametrize("name,get", INK_ON_GROUND, ids=[i[0] for i in INK_ON_GROUND])
def test_the_ink_is_darker_than_what_it_sits_on(name, get):
    """Rule 1 and rule 2 at once: nothing is lighter than its ground, and a
    light constant carried over from the dark theme onto a now-light surface is
    the commonest bug in this work (it gives 1.78:1)."""
    ink, ground = get()
    assert _lum(ink) < _lum(ground), f"{name}: {ink} is lighter than {ground}"


@pytest.mark.parametrize("name,get", INK_ON_GROUND, ids=[i[0] for i in INK_ON_GROUND])
def test_nothing_that_works_is_faint(name, get):
    """Rule 3 — low contrast means "disabled" and nothing else."""
    ink, ground = get()
    assert _contrast(ink, ground) >= 4.5


def test_the_render_badge_is_the_one_sanctioned_pairing():
    """The badge floats OVER the image, whose colour is anything at all, so it
    carries its own ground: ON_ACTION on an ACTION fill, 15.53:1. That is a
    fill, not inverted text — the single light-on-dark pairing the handoff
    allows, and the only place in these five files that uses it."""
    pal = TP._PREVIEW_NEUTRAL
    assert pal["badge_bg"] == N.NM_ACTION
    assert pal["badge_text"] == N.NM_ON_ACTION
    assert _contrast(pal["badge_text"], pal["badge_bg"]) > 15.0


def test_the_checked_proof_toggle_is_a_fill_not_an_inversion():
    pal = SPD._PALETTE_NEUTRAL
    assert pal["accent"] == N.NM_ACTION
    assert pal["on_accent"] == N.NM_ON_ACTION


# ======================================================================
# 4. One accent value, and it is ACTION
# ======================================================================

def test_every_accent_in_these_files_is_the_single_action_value():
    """Draft 1 "Index": one accent value on every accent surface. The violet
    that themed the gamut panel and the soft-proof, and the Measure green the
    marquee drew its ants in, are tab identities — and a colourless theme does
    not carry tab identity in a hue."""
    assert GP._PALETTE_NEUTRAL["accent"] == N.NM_ACTION
    assert SPD._PALETTE_NEUTRAL["accent"] == N.NM_ACTION
    assert SGM._ACCENT_BY_MODE[NEUTRAL].name() == N.NM_ACTION


def test_the_marquee_ants_get_an_under_stroke_only_in_neutral():
    """Green separated itself from any printed ink for free; a near-black ink
    does not, so in Neutral every stroke is drawn twice — first 2 px wider in
    the surface value. Light and Dark have no under-stroke and must not grow
    one."""
    assert SGM._UNDER_BY_MODE[NEUTRAL].name() == N.NM_BG_SURFACE
    assert SGM._UNDER_BY_MODE[LIGHT] is None
    assert SGM._UNDER_BY_MODE[DARK] is None


def test_the_under_stroke_actually_reaches_the_pixels(app, monkeypatch):
    """Not the table — the paint. Over a SOLID BLACK patch, which is where a
    near-black ant would otherwise vanish, the surface value has to appear.

    DIFFERENTIAL, not a membership test. It used to assert simply that
    BG_SURFACE was somewhere in the grab, which worked while the backdrop was
    BG_PANEL and the two were different colours. The owner collapsed the
    grounds onto one on 2026-09-02, and from that moment the backdrop alone
    satisfied the assertion: the test would have stayed green with the
    under-stroke deleted. So it now takes the same grab twice, with and
    without the stroke, and asks that the stroke put pixels on the screen.
    """
    def count(colour: str) -> int:
        black = QImage(400, 300, QImage.Format.Format_ARGB32)
        black.fill(QColor("#000000"))
        m = SGM.ScanGridMarquee()
        m.resize(400, 300)
        m.setPalette(N.make_neutral_palette())
        m.set_image(black)
        grab = m.grab().toImage()
        seen = [grab.pixelColor(x, y).name()
                for y in range(0, grab.height(), 2)
                for x in range(0, grab.width(), 2)]
        assert "#56d6a5" not in seen, "the Measure green survived in Neutral"
        return sum(1 for n in seen if n == colour)

    with_stroke = count(N.NM_BG_SURFACE)
    monkeypatch.setitem(SGM._UNDER_BY_MODE, NEUTRAL, None)
    without = count(N.NM_BG_SURFACE)
    assert with_stroke > without, (
        f"the under-stroke paints nothing: {with_stroke} px with it, "
        f"{without} px without")


def test_the_marquee_keeps_its_green_in_light_and_dark(app):
    from ui.light_styles import make_light_palette
    black = QImage(400, 300, QImage.Format.Format_ARGB32)
    black.fill(QColor("#000000"))
    m = SGM.ScanGridMarquee()
    m.resize(400, 300)
    m.setPalette(make_light_palette())
    m.set_image(black)
    grab = m.grab().toImage()
    seen = {grab.pixelColor(x, y).name()
            for y in range(0, grab.height(), 2)
            for x in range(0, grab.width(), 2)}
    assert "#56d6a5" in seen


# ======================================================================
# 5. The appearance is asked for by name, not measured
# ======================================================================

def test_the_marquee_asks_the_theme_for_the_appearance_by_name(app):
    """``is_dark`` cannot tell Neutral from Light — both are light grounds — and
    the backdrop, the accent and the under-stroke are three-way choices."""
    from ui.light_styles import make_light_palette
    from ui.styles import make_dark_palette
    m = SGM.ScanGridMarquee()
    for pal, expected in ((make_light_palette(), LIGHT),
                          (make_dark_palette(), DARK),
                          (N.make_neutral_palette(), NEUTRAL)):
        m.setPalette(pal)
        assert m._appearance() == expected


@pytest.mark.parametrize("mode,expected", [(LIGHT, "#efebe6"), (DARK, "#111111"),
                                           (NEUTRAL, N.NM_BG_PANEL)])
def test_the_empty_preview_paints_the_well_its_appearance_asks_for(app, mode, expected):
    """The EMPTY well — painted by the image label's own stylesheet."""
    w = TP.TiffPreview(None)
    w.resize(300, 240)
    w.set_appearance(mode)
    assert w.grab().toImage().pixelColor(150, 120).name() == expected


@pytest.mark.parametrize("mode,expected", [(LIGHT, "#efebe6"), (DARK, "#111111"),
                                           (NEUTRAL, N.NM_BG_PANEL)])
def test_the_loaded_preview_paints_the_same_well(app, tmp_path, mode, expected):
    """AND THE FULL ONE, WHICH IS A SECOND PAINT SITE ENTIRELY.

    The surround a zoomable chart sits in is the canvas fill inside
    ``_repaint_interactive``, not the image label's stylesheet — and the tabs'
    previews are all interactive. They were two separate two-way ternaries, and
    only one of them being fixed looks exactly like both being fixed until a
    chart is loaded, which is the state the owner is in every time he looks at
    this screen.
    """
    w = TP.TiffPreview(None)
    w.resize(420, 320)
    w.set_appearance(mode)
    w.set_interactive(True)          # as the tabs' previews are
    w.load_tiff([_chart_tiff(tmp_path)])
    # The label carries no layout in an unshown widget; give it a shape the
    # page cannot fill, so there is a real surround to measure.
    w._img_label.resize(300, 200)
    w._update_display()
    canvas = w._img_label.pixmap().toImage()
    assert canvas.pixelColor(2, 2).name() == expected


# ======================================================================
# 6. Light and Dark keep every value they had
# ======================================================================

def test_light_and_dark_preview_values_are_the_ones_they_shipped():
    """A regression fence. These are the literals the two shipped appearances
    painted before the frame was made theme-aware, transcribed from the code
    they replaced — including two that the OLD code never re-themed at all and
    so painted in both: the amber advisory banner and the #808080 ink readout.
    """
    assert TP._PREVIEW_LIGHT == {
        "caption": "#7a7570", "filename": "#7a7570", "page": "#7a7570",
        "img_bg": "#efebe6", "img_border": "#d0ccc6", "img_text": "#a8a4a0",
        "readout": "#808080",
        "banner_bg": "#f0c674", "banner_border": "#b88a2a", "banner_text": "#2a1a00",
        "badge_bg": "rgba(30, 30, 30, 185)", "badge_text": "#f4f2ef",
        "tip_bg": "#ffffff", "tip_text": "#22211f", "tip_border": "#d0ccc6",
        "tip_swatch_border": "#b8b3ad",
    }
    assert TP._PREVIEW_DARK == {
        "caption": "#808080", "filename": "#b8b8b8", "page": "#909090",
        "img_bg": "#111111", "img_border": "#333", "img_text": "#606060",
        "readout": "#808080",
        "banner_bg": "#f0c674", "banner_border": "#b88a2a", "banner_text": "#2a1a00",
        "badge_bg": "rgba(30, 30, 30, 185)", "badge_text": "#f4f2ef",
        "tip_bg": "#262626", "tip_text": "#e6e6e6", "tip_border": "#404040",
        "tip_swatch_border": "#5a5a5a",
    }


def test_light_and_dark_keep_the_violet_and_the_green():
    from ui.styles import SPEC_VIOLET
    assert GP._PALETTE_LIGHT["accent"] == SPEC_VIOLET
    assert GP._PALETTE_DARK["accent"] == SPEC_VIOLET
    assert SPD._PALETTE_LIGHT["accent"] == SPEC_VIOLET
    assert SPD._PALETTE_DARK["accent"] == SPEC_VIOLET
    assert SGM._ACCENT_BY_MODE[LIGHT].name() == "#56d6a5"
    assert SGM._ACCENT_BY_MODE[DARK].name() == "#56d6a5"
    assert SGM._BACKDROP_BY_MODE[LIGHT] == "#e8e8e8"
    assert SGM._BACKDROP_BY_MODE[DARK] == "#111"


def test_the_gamut_panel_does_not_restyle_a_light_or_dark_panel_at_build(app):
    """THE FAULT THAT IS DELIBERATELY LEFT IN PLACE.

    ``_build_ui`` styles the header and the profile line inline with the dark
    values, and ``set_appearance`` early-returns when handed the mode the panel
    was born with — so a panel born in Light keeps #8a8a8a and #b8b8b8 where
    the light palette says #7a7570. Calling ``_apply_mode_styles`` at build
    fixes it and moves 633 pixels of Light, which this change may not do. It is
    gated on the appearance being neither of the two shipped ones; this test is
    what stops the gate being quietly widened.
    """
    import inspect
    src = inspect.getsource(GP.GamutPanel.__init__)
    assert 'if self._mode not in ("light", "dark"):' in src
    assert "self._apply_mode_styles()" in src


# ======================================================================
# 7. The content is not repainted by the theme
# ======================================================================

def _count_content_differences(a: QImage, b: QImage, grounds) -> "tuple[int, int]":
    """How many pixels differ between two renders, ignoring each one's ground.

    The grounds differ — that is the whole change. Every other pixel is the
    user's own work and must be bit-identical. ``QColor.rgb()`` carries the
    alpha byte, so the masks are compared on RGB alone; forgetting that
    compares the grounds against each other and the test measures the change
    instead of the regression.
    """
    assert (a.width(), a.height()) == (b.width(), b.height())
    ground_rgb = {QColor(g).rgb() & 0xFFFFFF for g in grounds}
    compared = differing = 0
    for y in range(a.height()):
        for x in range(a.width()):
            pa, pb = a.pixel(x, y) & 0xFFFFFF, b.pixel(x, y) & 0xFFFFFF
            if pa in ground_rgb or pb in ground_rgb:
                continue
            compared += 1
            differing += (pa != pb)
    return differing, compared


def _chart_tiff(tmp_path):
    """A small chart-like page: a white sheet with saturated patches on it."""
    img = QImage(240, 180, QImage.Format.Format_RGB32)
    img.fill(QColor("#ffffff"))
    p = QPainter(img)
    for i, hexc in enumerate(("#ff0000", "#00ff00", "#0000ff", "#ffff00",
                              "#ff00ff", "#00ffff", "#000000", "#808080")):
        p.fillRect(20 + (i % 4) * 50, 30 + (i // 4) * 60, 40, 50, QColor(hexc))
    p.end()
    path = tmp_path / "chart_01.tif"
    assert img.save(str(path), "TIFF")
    return path


def test_the_chart_itself_is_identical_in_dark_and_neutral(app, tmp_path):
    """THE FAILURE THIS JOB CAN PRODUCE IS A WELL OF THE RIGHT COLOUR HOLDING
    THE WRONG PICTURE. So: render the same TIFF in Dark and in Neutral, and
    require every pixel that is neither appearance's ground to be identical.
    The grounds differ — that is the change. Nothing else may."""
    path = _chart_tiff(tmp_path)
    canvases = {}
    for mode in (DARK, NEUTRAL):
        w = TP.TiffPreview(None)
        w.resize(420, 320)
        w.set_appearance(mode)
        w.set_interactive(True)      # as the tabs' previews are
        w.load_tiff([path])
        w._img_label.resize(300, 200)
        # The repaint is debounced by 80 ms; the test does not wait for a timer
        # it can ask for directly.
        w._update_display()
        # The canvas the preview composes and hands to its image label: the
        # well, the paper frame and the chart, and nothing else. Comparing the
        # whole widget would drag in the caption, the page counter and the nav
        # buttons, which are chrome and differ on purpose.
        pm = w._img_label.pixmap()
        assert pm is not None and not pm.isNull(), "no canvas was composed"
        canvases[mode] = pm.toImage()
    differing, compared = _count_content_differences(
        canvases[DARK], canvases[NEUTRAL], ("#111111", N.NM_BG_PANEL))
    assert compared > 5000, "the chart never reached the canvas"
    assert differing == 0, f"{differing} of {compared} chart pixels were repainted"


def test_the_scan_image_itself_is_identical_in_dark_and_neutral(app, tmp_path):
    """The marquee's ants change by design; the scan under them does not."""
    path = _chart_tiff(tmp_path)
    img = QImage(str(path))
    from ui.styles import make_dark_palette
    grabs = {}
    for mode, pal in ((DARK, make_dark_palette()),
                      (NEUTRAL, N.make_neutral_palette())):
        m = SGM.ScanGridMarquee()
        m.resize(420, 320)
        m.setPalette(pal)
        m.set_image(img)
        m._corners = []          # no quad, no grid — the scan and its ground only
        grabs[mode] = m.grab().toImage()
    differing, compared = _count_content_differences(
        grabs[DARK], grabs[NEUTRAL], ("#111", N.NM_BG_PANEL))
    assert compared > 5000
    assert differing == 0, f"{differing} of {compared} scan pixels were repainted"


def test_the_gamut_scene_is_built_from_the_ground_it_is_handed(app):
    """The 3D gamut's geometry and hues come out of the .gam; the appearance
    supplies the page's ground and nothing else. Proved on the signature the
    panel actually calls with, so a value smuggled in beside the ground would
    show up here."""
    import inspect
    src = inspect.getsource(GP.GamutPanel)
    assert 'return self._palette()["frame_bg"]' in src
    # every consumer takes the ground from the one method, not from a literal
    assert src.count("self._current_bg()") >= 3
    assert '"#efebe6" if self._mode == "light"' not in src
