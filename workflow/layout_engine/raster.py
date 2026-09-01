"""Render the chart page TIFF(s) — Qt-free, via Pillow + tifffile.

Places each patch at the *same* slot the ``.ti2`` assigns it (shared seeded
permutation), so the printed raster and the measurement file can't disagree.
Draws colour patches, contrast-chosen spacers, and per-column strip indicators.
TIFFs are written in pixels-per-centimetre (ResolutionUnit=3) exactly like
printtarg, so the existing `page_geometry` / print pipeline read the DPI right.
"""
from __future__ import annotations

from functools import lru_cache

from dataclasses import dataclass, replace
from pathlib import Path

from core.stem_paths import artefact

import numpy as np
import tifffile
from PIL import Image, ImageDraw, ImageFont

from core.logger import get_logger
from core.resource_path import resource_path

from . import contrast, geometry, permutation
from .colorants import to_device_approx, to_device_approx_array, to_display_rgb
from .geometry import Layout

#: How thick the ruler helper markers are drawn (#152). Knut: *"a line thin
#: enough to be precise but visible — around 0.2 mm. Answer: sounds Good."*
_HELPER_MARKER_W_MM = 0.2
from .instruments import Geom
from .ti1_reader import ColorTarget

# THIS MODULE HAD NO LOGGER AND TWO HANDLERS THAT USED ONE.
#
# `log.warning(...)` in the helper-marker handler (shipped) and in the clip
# branding one (#164) both raised `NameError: name 'log' is not defined` — so
# the rescue that was supposed to keep a chart alive through a failed marker or
# a monstrous branding scale was itself the thing that killed it, and did so on
# the exact path that was already going wrong.
log = get_logger(__name__)

# Bundled free fonts available for on-chart text (OFL).
FONTS = {
    "JetBrains Mono": "assets/fonts/JetBrainsMono-VariableFont_wght.ttf",
    "Inter": "assets/fonts/Inter-VariableFont_opsz,wght.ttf",
    "Instrument Serif": "assets/fonts/InstrumentSerif-Regular.ttf",
}
# Static (non-variable) bundled families that ship separate style faces. The
# masthead's Instrument Serif has a real Italic file — using it (not a sheared
# regular) is what makes the "IQ" glyphs, e.g. the Q's tail, match the header.
FONT_STYLE_FILES = {
    "Instrument Serif": {"italic": "assets/fonts/InstrumentSerif-Italic.ttf"},
}
DEFAULT_INDICATOR_FONT = "JetBrains Mono"

# Masthead wordmark styling (ui.masthead_header): Instrument Serif, "Chrom" in
# near-black, "IQ" bold-italic in the magenta accent.
WORDMARK_FONT = "Instrument Serif"
WORDMARK_RGB = (28, 27, 24)     # #1c1b18 — light-mode "Chrom" colour
WORDMARK_IQ_RGB = (255, 69, 115)  # #ff4573 — magenta accent for "IQ"

# ChromIQ accent palette (ui.styles TAB_COLORS) as RGB, for the coloured
# under-indicator rule; cycled per strip so adjacent strips read distinctly.
# Printer-safe distance (mm) on-sheet text keeps from the page edge, so it isn't
# clipped by a printer's unprintable border (#93, Knut). Matches the clip-content
# inset so all text/labels share one safe edge.
TEXT_EDGE_MARGIN_MM = 4.0

ACCENT_RGB = (
    (255, 69, 115),    # magenta
    (255, 180, 45),    # amber
    (86, 214, 165),    # green
    (55, 188, 214),    # cyan
    (159, 130, 255),   # violet
)

_SYSTEM_FONT_MAP: dict[str, dict[str, str]] | None = None


def _system_font_dirs() -> list[Path]:
    import sys
    home = Path.home()
    if sys.platform == "darwin":
        return [Path("/System/Library/Fonts"), Path("/Library/Fonts"),
                home / "Library/Fonts"]
    if sys.platform.startswith("win"):
        import os
        return [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"]
    return [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
            home / ".fonts", home / ".local/share/fonts"]


def _style_key(subfamily: str) -> str:
    s = (subfamily or "").lower()
    b = "bold" in s
    i = "italic" in s or "oblique" in s
    return ("bolditalic" if b and i else "bold" if b else "italic" if i else "regular")


def _system_font_map() -> dict[str, dict[str, str]]:
    """Lazy family→{style: file} map for installed fonts.

    Per family we record which style faces exist (regular/bold/italic/
    bolditalic) so we can both render the right face *and* report truthfully
    which styles a font actually supports.
    """
    global _SYSTEM_FONT_MAP
    if _SYSTEM_FONT_MAP is not None:
        return _SYSTEM_FONT_MAP
    out: dict[str, dict[str, str]] = {}
    for d in _system_font_dirs():
        if not d.is_dir():
            continue
        for f in d.rglob("*"):
            if f.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                continue
            try:
                fam, sub = ImageFont.truetype(str(f), 12).getname()
            except Exception:
                continue
            out.setdefault(fam, {}).setdefault(_style_key(sub or ""), str(f))
    _SYSTEM_FONT_MAP = out
    return out


def _font_path(family: str, style: str = "regular") -> str | None:
    sf = FONT_STYLE_FILES.get(family)
    if sf and style in sf:
        return resource_path(sf[style])
    if family in FONTS:
        return resource_path(FONTS[family])
    faces = _system_font_map().get(family)
    if not faces:
        return None
    return faces.get(style) or faces.get("regular") or next(iter(faces.values()))


def font_supports(family: str) -> tuple[bool, bool]:
    """``(has_bold, has_italic)`` as the engine can actually render *family*.

    Bundled variable fonts are probed via their named instances; system fonts
    by which separate style faces are installed.  This is the single source of
    truth shared by the renderer and the UI's bold/italic enable logic.
    """
    if family in FONTS:
        # Static bundled family with separate style faces (e.g. Instrument Serif
        # ships a real Italic but no Bold).
        sf = FONT_STYLE_FILES.get(family)
        if sf is not None:
            return ("bold" in sf or "bolditalic" in sf,
                    "italic" in sf or "bolditalic" in sf)
        try:
            f = ImageFont.truetype(resource_path(FONTS[family]), 12)
            low = [(_n.decode() if isinstance(_n, bytes) else _n).replace(" ", "").lower()
                   for _n in f.get_variation_names()]
        except Exception:
            return (False, False)
        return (any("bold" in n for n in low),
                any(("italic" in n or "oblique" in n) for n in low))
    faces = _system_font_map().get(family, {})
    return ("bold" in faces or "bolditalic" in faces,
            "italic" in faces or "bolditalic" in faces)


def _font(px: int, family: str = DEFAULT_INDICATOR_FONT,
          bold: bool = False, italic: bool = False
          ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    style = ("bolditalic" if bold and italic else "bold" if bold
             else "italic" if italic else "regular")
    path = _font_path(family, style) or resource_path(FONTS[DEFAULT_INDICATOR_FONT])
    try:
        f = ImageFont.truetype(path, max(6, px))
    except Exception:  # pragma: no cover - font load fallback
        return ImageFont.load_default()
    if bold or italic:
        want = ("Bold Italic" if bold and italic else "Bold" if bold else "Italic")
        want_key = want.replace(" ", "").lower()
        try:    # variable fonts (our bundled ones) expose named instances
            for n in f.get_variation_names():
                name = n.decode() if isinstance(n, bytes) else n
                if name.replace(" ", "").lower() == want_key:
                    f.set_variation_by_name(n)
                    break
        except Exception:
            pass    # static font without that instance — render regular
    return f


def _font_file_and_variation(family: str, bold: bool, italic: bool
                             ) -> tuple[str | None, str | None]:
    """The font file path + variable-instance name the renderer uses for
    *family*/*style* — so the vector-PDF text can load the exact same face."""
    style = ("bolditalic" if bold and italic else "bold" if bold
             else "italic" if italic else "regular")
    path = _font_path(family, style)
    variation = None
    if bold or italic:
        variation = ("Bold Italic" if bold and italic else "Bold" if bold
                     else "Italic")
    return path, variation


_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Tiny gap inserted between letters of a multi-letter strip label (e.g. "AB"),
# as a fraction of the font size, so the two letters stay distinguishable.
INDICATOR_LETTER_SPACING = 0.12
# Auto-sized multi-letter labels fill only this fraction of the strip width, so
# the inter-indicator gap exceeds the intra-letter gap (#93).
INDICATOR_FIT_FRAC = 0.80
INDICATOR_MIN_LEGIBLE_MM = 1.5   # auto-size floor — smaller is unreadable in print


def _draw_indicator(draw, cx: int, top: int, text: str, font, spacing_px: int) -> None:
    """Draw a strip label centred at *cx*, with a small gap between letters so a
    two-letter label (e.g. "AB") stays legible."""
    if len(text) <= 1 or spacing_px <= 0:
        try:
            draw.text((cx, top), text, font=font, fill=(0, 0, 0), anchor="ma")
        except Exception:             # default bitmap font: no anchor support
            tw = int(draw.textlength(text, font=font))
            draw.text((cx - tw // 2, top), text, font=font, fill=(0, 0, 0))
        return
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + spacing_px * (len(text) - 1)
    x = cx - total / 2
    for ch, w in zip(text, widths):
        try:
            draw.text((x, top), ch, font=font, fill=(0, 0, 0), anchor="la")
        except Exception:             # default bitmap font: top-left default
            draw.text((x, top), ch, font=font, fill=(0, 0, 0))
        x += w + spacing_px


def _indicator_tile(text: str, font, spacing_px: int, degrees: int) -> Image.Image:
    """A transparent tile of the strip label (letters spaced) rotated *degrees*."""
    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    widths = [probe.textlength(c, font=font) for c in text]
    try:
        asc, desc = font.getmetrics()
    except Exception:  # pragma: no cover - default bitmap font
        asc, desc = 12, 3
    W = int(sum(widths) + spacing_px * (len(text) - 1)) + 4
    H = asc + desc + 4
    tile = Image.new("RGBA", (max(1, W), max(1, H)), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    x = 2.0
    for ch, w in zip(text, widths):
        d.text((x, 2), ch, font=font, fill=(0, 0, 0, 255))
        x += w + spacing_px
    if degrees % 360:
        tile = tile.rotate(degrees, expand=True)   # CCW; 90 reads bottom-to-top
    return tile


@lru_cache(maxsize=256)
def _widest_upper_px(px: int, font: str) -> float:
    """The width of the widest capital letter, in pixels, at *px* in *font*.

    MEASURED ONCE PER (SIZE, FONT), NOT 1,170 TIMES A KEYSTROKE. The answer —
    how wide is a capital letter in JetBrains Mono at 83 px — cannot change, and
    this is on the hot path of every layout solve: `_fit_columns` binary-searches
    40 iterations, each a full geometry, each measuring all 26 letters. Typing
    one character into the Manual name field ran 51,480 PIL text measurements
    and cost 76 ms of the 82 ms a keystroke took; two cache entries covered a
    whole session.

    Verified side-effect-free before it went in: the memoised value was compared
    with the live one over 2,250 consecutive calls with zero differences, and a
    deliberately wrong variant was caught 225 times by the same comparator.
    """
    f = _font(px, font)
    return max(f.getlength(c) for c in _UPPER)


def effective_indicator_size_mm(geom, dpi: int, font: str, size_mm: float) -> float:
    """The indicator font size to use. An explicit *size_mm* is returned as-is;
    *size_mm* 0 = auto, where the size is chosen so the widest two-letter label
    (plus the inter-letter gap) fits the strip width (capped at the instrument
    text height)."""
    if size_mm:
        return float(size_mm)
    mm2px = dpi / 25.4
    target = geom.txhisl
    try:
        widest2 = (2.0 * _widest_upper_px(max(6, round(target * mm2px)), font) / mm2px
                   + INDICATOR_LETTER_SPACING * target)   # + one inter-letter gap
    except Exception:
        return target
    # Fit the label into a FRACTION of the strip width, not the whole width, so
    # the gap BETWEEN indicators stays larger than the gap between the two
    # letters of one indicator (otherwise "AA AB" reads as "A AA B"). (#93)
    avail = geom.pwid * INDICATOR_FIT_FRAC
    if widest2 <= avail:
        return target
    # Never shrink below legibility: with a wide proportional font on a
    # narrow-patch chart the fit collapsed to a fraction of a millimetre —
    # labels so small a user thought they were switched off (#108 follow-up).
    # A slightly-too-wide label beats an invisible one; the preflight
    # too-wide warning still tells the user why.
    return max(min(target, INDICATOR_MIN_LEGIBLE_MM), target * avail / widest2)


def _furniture_reserves_mm(geom, kw: dict) -> tuple[float, float]:
    """``(label_band_mm, bottom_reserve_mm)`` — the vertical space the rendered
    strip-label band (indicator + underline) and the bottom sheet-text/stamp
    block actually consume, so :func:`geometry.compute` can reserve them.

    An auto-sized upright indicator measures its *ink* height (≈ cap height),
    which stays under the instrument ``txhisl`` so default charts keep
    printtarg-parity capacity; a big, rotated, or underlined label grows the band
    and reduces the count instead of overlapping the patches (#93).
    """
    dpi = int(kw.get("dpi") or 150)
    mm2px = dpi / 25.4
    label_band = 0.0   # indicators off ⇒ reclaim the whole label band
    if kw.get("draw_indicators", True):
        fam = kw.get("indicator_font", DEFAULT_INDICATOR_FONT)
        raw_size = float(kw.get("indicator_size_mm") or 0.0)   # 0 = auto
        size_mm = effective_indicator_size_mm(geom, dpi, fam, raw_size)
        ind_px = max(6, round(size_mm * mm2px))
        f = _font(ind_px, fam, bool(kw.get("indicator_bold")),
                  bool(kw.get("indicator_italic")))
        rot = int(kw.get("indicator_rotation") or 0) % 360
        spc = max(1, round(ind_px * INDICATOR_LETTER_SPACING))
        if rot in (90, 270):
            # Side-rotated: the band runs along the strip, so its height is the
            # label's drawn length. Reserve for up to two letters (≤702 strips).
            band_px = _indicator_tile("WW", f, spc, rot).height
        else:
            # Upright: the visible ink height of representative cap/digit glyphs.
            probe = Image.new("RGBA", (ind_px * 4, ind_px * 4), (0, 0, 0, 0))
            ImageDraw.Draw(probe).text((ind_px, ind_px), "W8", font=f,
                                       fill=(0, 0, 0, 255))
            bb = probe.getbbox()
            band_px = (bb[3] - bb[1]) if bb else ind_px
        band = band_px / mm2px
        if kw.get("underline_mode", "off") in ("segments", "cycle", "black", "colored"):
            band += (float(kw.get("underline_gap_mm") or 0.0)
                     + max(0.0, float(kw.get("underline_thickness_mm") or 0.0)))
        # Auto size keeps the instrument label floor (txhisl) so default charts
        # stay printtarg-identical; an EXPLICIT size reserves exactly what it
        # draws, so a smaller font frees space for more patches (#93).
        label_band = band if raw_size > 0 else max(geom.txhisl, band)
    # Bottom-of-sheet block: one line each for custom sheet text and the stamp,
    # drawn at line_h = px(4.2) above the printer-safe bottom inset (see
    # render_pages); the inset keeps the text clear of a printer's unprintable
    # edge (#93, Knut's "distance from page edge to text").
    nlines = (1 if kw.get("chart_text") else 0) + (1 if kw.get("stamp_command") else 0)
    _edge = float(kw.get("text_edge") or TEXT_EDGE_MARGIN_MM)
    bottom = (_edge + 4.2 * nlines) if nlines else 0.0
    return label_band, bottom


def apply_furniture_reserves(geom, kw: dict):
    """Return *geom* with label_band_mm / bottom_reserve_mm filled from the
    rendered furniture (single source of truth shared by the renderer and every
    capacity estimate, so they can't disagree — #93)."""
    lb, br = _furniture_reserves_mm(geom, kw)
    return apply_row_label_geometry(
        replace(geom, label_band_mm=lb, bottom_reserve_mm=br), kw)


#: What `LayoutRecipe.text_edge_clip_mm` defaults to. Kept here as well because
#: the row-label floor is read from build kwargs that are sometimes assembled
#: by hand, where a missing key would otherwise mean "zero".
_DEFAULT_TEXT_EDGE_CLIP_MM = 4.0


def apply_row_label_geometry(geom, kw: dict):
    """Size the row-label band to its labels, and raise the left margin to hold
    it — `docs/design/row_label_geometry.md` §R2.

    Five rules from Knut, one derivation:

      * the band is measured from the WIDEST label actually printed, at the
        chosen text size, plus 1 mm (§R1.2) -- it was a fixed 7.5 mm, too wide
        for a 9-row chart at 6 pt (2.27 mm needed) and far too narrow for 120
        rows at 24 pt (16.24 mm), where the labels walked off the paper;
      * it may never come closer to the page edge than the clip border, or the
        text-distance-to-edge where there is no border (§R1.3);
      * so the LEFT MARGIN is raised to hold it, never lowered (§R1.5);
      * and the band then lives INSIDE that margin, so the patch area still
        starts exactly at the margin in both layout modes (§R1.4). That is why
        no capacity calculation subtracts `rlwi` any more.

    Returns the geometry unchanged when there are no row labels.
    """
    band = float(getattr(geom, "rlwi", 0.0) or 0.0)
    if band <= 0:
        return geom
    measured = row_label_band_mm(
        geom, dpi=int(kw.get("dpi") or 300),
        indicator_font=kw.get("indicator_font") or DEFAULT_INDICATOR_FONT,
        indicator_size_mm=float(kw.get("indicator_size_mm") or 0.0),
        indicator_bold=bool(kw.get("indicator_bold")),
        indicator_italic=bool(kw.get("indicator_italic")),
        patch_pattern=kw.get("patch_pattern") or "")
    if measured <= 0:
        return geom
    # §R1.3's floor: the clip border when one sits on this edge, otherwise the
    # distance-to-edge the user set for furniture.
    on_left = (str(kw.get("clip_side") or "left") == "left")
    # `lbord` says WHETHER a clip border is on this edge; it is not how wide it
    # is (26 mm of border comes back as lbord = 20). Using it as the floor put
    # the labels at 21 mm on a 26 mm border, so the border printed over their
    # left half and only slivers came out -- visible on the rendered page.
    # `Geom.has_clip_border` already answers this — it is the field the band
    # gate itself uses — so nothing new has to be threaded through the build.
    has_border = on_left and bool(getattr(geom, "has_clip_border", False)) \
        and float(getattr(geom, "lbord", 0.0) or 0.0) > 0
    # WHAT THE LABELS MUST CLEAR — §R1.3, and it is Knut's rule, not a
    # convenience: *"Row labels may never come closer to the page edge than
    # the Clip limit, mirroring the rule that strip labels may not pass T."*
    #
    # So the floor is the Clip distance always, and the whole width of a clip
    # border when one is drawn on this edge (a border prints over anything
    # under it), and any instrument leader. This costs patch area on a chart
    # with row indicators — the margin is raised to make room — which is the
    # trade §R1.4 asks for: the labels stay on the paper and the patches stay
    # inside the margins, so the paper pays rather than the data.
    # THE RECIPE'S DEFAULT WHEN THE KEY IS ABSENT, not zero. Several callers
    # build these kwargs by hand — the Guided capacity estimate among them —
    # and a missing key must not quietly produce a different geometry from the
    # one the build uses. It did: the estimate came out with a 10.43 mm left
    # margin against the build's 14.43 mm and promised 368 patches on a CR30
    # A4 sheet that holds 345 (Basti, 2026-09-01).
    _edge = kw.get("text_edge_clip")
    # ONLY WHAT IS ACTUALLY ON THE LEFT. `lbord` is the furniture band's width
    # wherever that band sits, so counting it unconditionally raised the LEFT
    # margin by 20 mm for a clip border on the RIGHT — 81 patches off an A4
    # sheet, for something the labels never had to clear.
    _left_furniture = (float(getattr(geom, "lbord", 0.0) or 0.0)
                       if on_left else 0.0)
    floor = max(_left_furniture,
                float(_DEFAULT_TEXT_EDGE_CLIP_MM if _edge is None else (_edge or 0.0)),
                float(kw.get("clip_border_width") or 0.0) if has_border else 0.0)
    needed = floor + measured + 1.0
    margin_l = max(float(getattr(geom, "margin_l", 0.0) or 0.0), needed)
    return replace(geom, rlwi=measured, margin_l=margin_l)


def _rows_that_fit(geom, kw: dict) -> int:
    """How many patch rows a full page holds — the count of labels drawn.

    Taken from the geometry rather than the chart's patch count, because the
    band has to hold the widest label a FULL page would print; a short chart
    simply uses part of it.

    The paper comes from the build kwargs: `Geom` does not carry it (the size
    is handed to `geometry.compute`), and defaulting to A4 here would size the
    band for the wrong sheet on Letter or A3 without anything saying so.
    """
    pitch = float(getattr(geom, "plen", 0.0) or 0.0) + \
        float(getattr(geom, "pspa", 0.0) or 0.0)
    if pitch <= 0:
        return 0
    from . import papers
    try:
        _w, h_mm = papers.dimensions_mm(kw.get("paper") or "A4")
    except Exception:              # noqa: BLE001 — an unknown paper is not fatal
        return 0
    if str(kw.get("orientation") or "").lower().startswith("land"):
        _w, h_mm = h_mm, _w
    usable = (h_mm
              - float(getattr(geom, "margin_t", 0.0) or 0.0)
              - float(getattr(geom, "margin_b", 0.0) or 0.0)
              - float(getattr(geom, "label_band_mm", 0.0) or 0.0)
              - float(getattr(geom, "bottom_reserve_mm", 0.0) or 0.0))
    return max(1, int(usable / pitch)) if usable > 0 else 0


def clip_text_lines(text: "str | None") -> list[str]:
    """Custom clip-border text split into rendered lines — EVERY line kept.

    Blank lines are writing space: a hand fills in the underscored fields, and
    the gaps are where it writes. Interior blanks were always kept; leading and
    trailing ones were trimmed, which Knut asked for in beta.28 and then asked
    to have back on 2026-08-23, having found the limit in use:

        *"The text field no longer allows empty line to be shown, either on
        first line, last line or between lines. This limits how user wants to
        present the text lines with spaces between lines. This should be allowed
        for all Content options where text field can be used."*

    So the text is now rendered as it was typed. Text that is ONLY whitespace is
    still nothing at all — a band of blank lines is an empty band, not a tall
    one.

    `splitlines()` IS NOT "AS IT WAS TYPED" — it treats a final newline as a
    terminator rather than a separator, so `"A\n"` comes back as `['A']` and
    the one thing beta.3 did not restore was the blank line at the END:

        "A"       -> ['A']
        "A\n"     -> ['A']        <- one trailing Enter, the blank line lost
        "A\n\n"   -> ['A', '']

    Knut found the gap and a workaround for it — a space on the last line does
    come through (#164). It is not a good one: the space is invisible, nobody
    would discover it, and any editor that strips trailing whitespace throws it
    away. `split("\n")` keeps what was typed, and the whitespace-only guard
    below still turns a band of nothing into nothing.
    """
    lines = (text or "").split("\n")
    return lines if any(ln.strip() for ln in lines) else []


def render_clip_strip(mode: str, *, width_px: int, height_px: int, dpi: int,
                      text: str = "", font_family: str = "Inter",
                      image_path: str = "", ctx: dict | None = None,
                      image_rotation: int = 0, image_scale: float = 100.0,
                      image_offset_x_mm: float = 0.0,
                      image_offset_y_mm: float = 0.0,
                      image_obj: "Image.Image | None" = None,
                      text_size_mm: float = 0.0) -> Image.Image:
    """Render the left clip-strip content as a ``width_px × height_px`` image.

    The strip is tall and narrow, so text/branding are drawn on a landscape
    canvas and rotated 90° to read up the strip. Shared by the page renderer and
    the standalone template export.

    *ctx* supplies the auto-filled values for the ``notes`` design (patch count,
    instrument, paper, page, profile name, date…); when absent a sample is used
    so the panel preview / template export still shows the layout (#93).
    """
    mm2px = dpi / 25.4
    strip = Image.new("RGB", (max(1, width_px), max(1, height_px)), (255, 255, 255))

    if mode == "image" and (image_path or image_obj is not None):
        try:
            # A pre-loaded (and possibly downscaled) image lets the panel preview
            # stay smooth on a big file; generation passes the path = full quality.
            logo = (image_obj if image_obj is not None
                    else Image.open(image_path)).convert("RGBA")
            if image_rotation % 360:
                logo = logo.rotate(image_rotation % 360, expand=True,
                                   resample=Image.BICUBIC)
            # Scale = fit-to-band × the user's percent (100 = fit), then move.
            fit = min(width_px / logo.width, height_px / logo.height)
            scale = fit * max(0.05, (image_scale or 100.0) / 100.0)
            nw, nh = max(1, int(logo.width * scale)), max(1, int(logo.height * scale))
            logo = logo.resize((nw, nh))
            cx = (width_px - nw) // 2 + round(image_offset_x_mm * mm2px)
            cy = (height_px - nh) // 2 + round(image_offset_y_mm * mm2px)
            strip.paste(logo, (cx, cy), logo)
        except Exception:  # pragma: no cover - bad/missing image falls back blank
            pass
        # AN IMPORTED IMAGE MAY CARRY TEXT TOO (#164, Knut: *"Content option
        # 'imported image' has text field disabled, but should allow adding
        # text"*). Drawn over the image, the same way the branding draws its
        # lines, so a logo can be captioned without leaving the app.
        lines = clip_text_lines(text)
        if lines:
            overlay = _vtext("\n".join(lines), font_family, width_px, height_px,
                             size_px=(text_size_mm * mm2px) if text_size_mm else 0.0)
            strip.paste(overlay, (0, 0), overlay)
        return strip

    if mode == "notes":
        return _render_notes_strip(width_px, height_px, dpi, ctx, font_family)

    if mode == "branding":
        # …and the branding's lines are kept the same way. This one dropped
        # blank lines ANYWHERE, interior ones included, so the wordmark's own
        # caption could not be spaced at all (#164).
        extra = clip_text_lines(text)
        try:
            overlay = _vwordmark(extra, width_px, height_px, font_family,
                                 extra_size_px=(text_size_mm * mm2px) if text_size_mm else 0.0,
                                 scale=image_scale,
                                 offset_x_px=image_offset_x_mm * mm2px,
                                 offset_y_px=image_offset_y_mm * mm2px)
        except Exception:  # noqa: BLE001 — a blank band, never a crashed slot
            # The imported-image branch above has always swallowed its failures;
            # the branding one could not fail until it gained a scale, and then
            # an extreme one took the whole repaint down with it (#164).
            log.warning("could not render the clip branding", exc_info=True)
            return strip
        strip.paste(overlay, (0, 0), overlay)
        return strip

    # plain text → rotated text up the strip. Blank lines are writing space — for
    # a hand to fill in the underscored fields — so every line the user typed is
    # kept, wherever it is: first, last or between (#164; the earlier rule
    # trimmed the leading and trailing ones, and Knut asked for them back).
    lines = clip_text_lines(text)
    if not lines:
        return strip
    overlay = _vtext("\n".join(lines), font_family, width_px, height_px,
                     size_px=(text_size_mm * mm2px) if text_size_mm else 0.0)
    strip.paste(overlay, (0, 0), overlay)
    return strip


def _italic_tile(text: str, font, fill: tuple, stroke_w: int = 0,
                 shear: float = 0.22) -> tuple[Image.Image, int, int]:
    """Render *text* sheared right (faux-italic) on a baseline-aware tile.

    Returns ``(image, baseline_y, left_x)`` where *baseline_y* is the row the
    text sits on (unchanged by the horizontal shear) and *left_x* is the first
    inked column — so the caller can align it to another glyph's baseline and
    butt it up tightly.
    """
    asc, desc = font.getmetrics()
    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    w = int(probe.textlength(text, font=font))
    pad = stroke_w + 3
    W, H = w + pad * 2, asc + desc + pad * 2
    base_y = pad + asc
    tile = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((pad, base_y), text, font=font, fill=fill,
                              stroke_width=stroke_w, stroke_fill=fill, anchor="ls")
    if not shear:                       # real italic face → no faux slant/resample
        bbox = tile.getbbox()
        return tile, base_y, (bbox[0] if bbox else 0)
    # AFFINE maps output→input: input_x = x + shear*(H - y) leans the top right.
    sheared = tile.transform((W + int(H * shear), H), Image.AFFINE,
                             (1, shear, -shear * H, 0, 1, 0), resample=Image.BICUBIC)
    bbox = sheared.getbbox()
    return sheared, base_y, (bbox[0] if bbox else 0)


#: The clip band's usable share across (0.92) and along it (0.99). The clip AREA
#: already keeps the text-edge distance from the page edge, so don't inset twice.
_CLIP_ACROSS, _CLIP_ALONG = 0.92, 0.99
#: The wordmark is protected down to an equal share of the band — but never asks
#: for more than this fraction of its unconstrained size, so a user who sets a
#: big clip-text size with one or two lines keeps the size they asked for (#163).
_WORDMARK_FLOOR_FRAC = 0.40
_BRANDING_MIN_PX = 8
#: How far past the band's own width the branding may be scaled (#164). The
#: wordmark is laid ACROSS the band, so a few times its width is already one
#: giant letter; beyond that a glyph tile is large enough for Pillow to refuse
#: it outright, and the refusal used to surface as a crash out of a Qt slot.
_MAX_BRANDING_SIZE_FACTOR = 4.0
#: …and an absolute ceiling on top of that, because a share of the band is not
#: a bound at all on a wide one: a 100 mm clip band (the spin box's maximum) at
#: 1200 dpi is 4535 px, four times which asks Pillow for a 257-megapixel glyph —
#: over its 179 Mpx limit, so the mark vanished instead of merely being huge.
#: 4000 px is ~85 mm of single letter at 1200 dpi; nothing legitimate is near it,
#: and the glyph tile it implies (~46 Mpx) stays under Pillow's WARNING threshold
#: as well as its hard limit — an alarming message on stderr is not a fix either.
_MAX_BRANDING_SIZE_PX = 4000.0


def _fit_branding_sizes(extra_lines: list[str], width_px: int, height_px: int,
                        font_family: str = "Inter",
                        extra_size_px: float = 0.0) -> tuple[int, int]:
    """Font sizes for the branding clip band: ``(wordmark, extra lines)``.

    Split out of the drawing so the RULE can be tested exactly instead of being
    inferred from ink (#163).

    With no clip-text size set, one size serves the whole stack and shrinks to
    fit — the long-standing automatic behaviour, left untouched.

    With a size set, the wordmark gives way first: it shrinks until it reaches
    its floor, and only then do the user's lines shrink with it. Both sizes are
    SOLVED rather than stepped down: the old loop stepped 40 × 0.95, which
    bottoms out at ×0.129, so a size far above what the band can hold still
    overflowed and printed off the edge of the sheet.

    The two axes are kept apart. Across the band the wordmark and the lines
    share one budget. ALONG the strip each is limited only by its own longest
    line — otherwise a long line of the user's shrinks the wordmark it does not
    crowd, and a long wordmark crushes the user's text to nothing.
    """
    d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    k = len(extra_lines)
    n = 1 + k
    across, along = width_px * _CLIP_ACROSS, height_px * _CLIP_ALONG
    natural = width_px * 0.55

    if not extra_size_px:
        # AUTO: one size for wordmark and lines alike, shrunk to fit. Unchanged
        # — this is the default, and it was never what #163 was about.
        size = max(10, int(natural))
        for _ in range(40):
            f = _font(size, WORDMARK_FONT)
            f_extra = _font(size, font_family)
            wm_w = d.textlength("Chrom", font=f) + d.textlength("IQ", font=f) * 1.25
            widest = max([wm_w] + [d.textlength(l, font=f_extra) for l in extra_lines])
            if size * 1.25 * n <= across and widest <= along:
                break
            size = int(size * 0.9)
            # The floor used to be 10 px, and the loop left the stack OVER the
            # band when even 10 px could not fit it — a narrow band with several
            # lines then printed them off the edge. Every case that already
            # fitted breaks out above and is untouched (#163).
            if size <= _BRANDING_MIN_PX:
                size = _BRANDING_MIN_PX
                break
        return size, size

    # Advance widths scale linearly with the point size, so one measurement at a
    # reference size gives the largest size each block may take along the strip.
    ref = 100
    f_ref = _font(ref, WORDMARK_FONT)
    wm_ref = (d.textlength("Chrom", font=f_ref)
              + d.textlength("IQ", font=f_ref) * 1.25)
    txt_ref = max((d.textlength(l, font=_font(ref, font_family))
                   for l in extra_lines), default=0.0)
    size_along = (along * ref / wm_ref) if wm_ref > 0 else float(width_px)
    esize_along = (along * ref / txt_ref) if txt_ref > 0 else float(width_px)

    size = min(natural, size_along)
    esize = min(float(extra_size_px), esize_along)
    if size * 1.25 + k * esize * 1.25 > across:
        floor = min(across / n / 1.25, natural * _WORDMARK_FLOOR_FRAC, size_along)
        size = max(min(size, (across - k * esize * 1.25) / 1.25), floor)
        if k and size * 1.25 + k * esize * 1.25 > across:
            esize = (across - size * 1.25) / (k * 1.25)
    return (max(_BRANDING_MIN_PX, int(size)),
            max(_BRANDING_MIN_PX, int(esize)))


def _vwordmark(extra_lines: list[str], width_px: int, height_px: int,
               font_family: str = "Inter", extra_size_px: float = 0.0,
               scale: float = 100.0, offset_x_px: float = 0.0,
               offset_y_px: float = 0.0) -> Image.Image:
    """The masthead "ChromIQ" wordmark — Instrument Serif, "Chrom" near-black,
    "IQ" bold-italic in magenta — plus optional lines, read up the strip. The
    optional lines use *font_family* (the user's chosen clip font), not the
    wordmark face (#93, Knut).

    *extra_size_px* > 0 sets the point size of the optional lines (the user's
    clip-text Size, which now applies to branding too — Knut); 0 keeps the
    legacy behaviour of matching the wordmark's auto-fit size.

    *scale* (percent) and the two offsets place the block, the same way the
    imported image is placed (#164, Knut: *"For Imported image option, then
    there are fields to position the image. Why are those options not available
    for ChromIQ branding? Currently the image is always centred on page
    vertically and text on next line."*). The scale multiplies the size the
    fitter SOLVED, so :func:`_fit_branding_sizes` — and the #163 rules it
    encodes — are untouched at 100 %, and a bigger number is the user asking
    for a bigger mark rather than a bug in the fit.
    """
    canvas = Image.new("RGBA", (max(1, height_px), max(1, width_px)), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    chrom_fill = WORDMARK_RGB + (255,)
    iq_fill = WORDMARK_IQ_RGB + (255,)
    size, _esize = _fit_branding_sizes(extra_lines, width_px, height_px,
                                       font_family, extra_size_px)
    sc = max(0.05, float(scale or 100.0) / 100.0)
    if sc != 1.0:
        # CEILING, NOT JUST A FLOOR. The Scale box runs to 50 000 % because it
        # was built for blowing a small logo up, and multiplying a SOLVED font
        # size by that allocates a glyph tile of ~194 million pixels — Pillow
        # refuses it as a decompression bomb, and the exception came out of a Qt
        # slot while the user was typing in a spin box. Past a few times the
        # band's width the mark is one letter anyway, so the extra is refused
        # here rather than paid for.
        ceiling = max(_BRANDING_MIN_PX * 2.0,
                      min(_MAX_BRANDING_SIZE_FACTOR * width_px,
                          _MAX_BRANDING_SIZE_PX))
        size = min(ceiling, max(_BRANDING_MIN_PX, size * sc))
        _esize = min(ceiling, max(_BRANDING_MIN_PX, _esize * sc))
    esize = _esize if extra_size_px else None
    f = _font(size, WORDMARK_FONT)
    asc, desc = f.getmetrics()
    line_h = size * 1.25
    extra_line_h = (esize if esize else size) * 1.25
    # Centre the whole stack (wordmark line + extra lines at their own height).
    stack_h = line_h + len(extra_lines) * extra_line_h
    cy = (width_px - stack_h) / 2
    # "IQ" is the masthead's real Instrument Serif *Italic* face (the masthead
    # asks for bold too, but Instrument Serif has no bold face and Qt doesn't
    # synthesise one — so the header renders plain italic). Use the genuine
    # italic glyphs (no faux shear, no faux bold) so the "IQ" — notably the Q's
    # tail — matches the header exactly instead of a sheared regular face.
    f_iq = _font(size, WORDMARK_FONT, italic=True)
    iq_tile, iq_base, iq_left = _italic_tile("IQ", f_iq, iq_fill, shear=0.0)
    chrom_w = d.textlength("Chrom", font=f)
    kern = size * 0.02
    wm_w = chrom_w + kern + (iq_tile.width - iq_left)
    x = (height_px - wm_w) / 2
    # Share one baseline so "IQ" sits level with "Chrom" (not raised).
    baseline = cy + line_h * 0.5 + (asc - desc) / 2
    try:
        d.text((x, baseline), "Chrom", font=f, fill=chrom_fill, anchor="ls")
        canvas.paste(iq_tile,
                     (int(x + chrom_w + kern - iq_left), int(baseline - iq_base)),
                     iq_tile)
        f_extra = _font(esize if esize else size, font_family)  # user's clip font + size
        for i, ln in enumerate(extra_lines):
            ly = cy + line_h + extra_line_h * (i + 0.5)
            d.text((height_px / 2, ly), ln, font=f_extra,
                   fill=chrom_fill, anchor="mm")
    except Exception:  # pragma: no cover - default font without anchor
        d.text((x, baseline), "ChromIQ", font=f, fill=chrom_fill)
    out = canvas.rotate(90, expand=True)
    if not (offset_x_px or offset_y_px):
        return out
    # Move it exactly the way the imported image is moved: X across the band,
    # Y along the strip, applied to the finished overlay so nothing about the
    # fit changes. Content pushed past the band is cropped, as it is for an
    # image — the preview shows that happening before it reaches paper.
    moved = Image.new("RGBA", out.size, (0, 0, 0, 0))
    moved.paste(out, (round(offset_x_px), round(offset_y_px)), out)
    return moved


def _vtext(text: str, font_family: str, width_px: int, height_px: int,
           *, valign: str = "center", bold: bool = False,
           size_px: float = 0.0) -> Image.Image:
    """A transparent ``width_px × height_px`` overlay with *text* read up the strip.

    ``size_px`` (>0) fixes the font size the user chose instead of auto-fitting
    to the strip width; the shrink-to-fit loop below still caps it so the text
    can never overrun the strip (#125, Knut — manual clip-text size)."""
    # Draw on a landscape canvas (long = height_px, short = width_px), rotate 90°.
    canvas = Image.new("RGBA", (max(1, height_px), max(1, width_px)), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    lines = text.split("\n")
    n = max(1, len(lines))
    # The clip AREA already sits the clip text-edge distance in from the page edge
    # on EVERY side (geometry.clip_area_mm), so fill it: THICK across the strip
    # (the stacked lines), LEN along it (the longest line). A small hair guards
    # glyph overshoot. (Knut: the text must reach the text-edge on the sides too,
    # not just top/bottom.)
    THICK, LEN = 0.98, 0.995
    if size_px and size_px > 0:
        size = max(8, int(size_px))                      # manual size (#125)
    else:
        # AUTO: GROW the font to the largest size that fills both axes — measured
        # once at a reference size and scaled (advance widths scale linearly), so
        # it reaches the text-edge instead of stopping at a fixed fraction of the
        # strip width (the old start-and-only-shrink capped it well short — Knut).
        ref = 100
        fref = _font(ref, font_family, bold=bold)
        widest_ref = max((d.textlength(ln, font=fref) for ln in lines),
                         default=1.0) or 1.0
        size_thick = (width_px * THICK) / (1.2 * n)
        size_len = ref * (height_px * LEN) / widest_ref
        size = max(8, int(min(size_thick, size_len)))
    f = _font(size, font_family, bold=bold)
    # Safety: shrink if rounding pushed a hair over (never grows past the fill
    # size); also caps a too-large manual size so text can't overrun the strip.
    for _ in range(40):
        f = _font(size, font_family, bold=bold)
        line_h = size * 1.2
        block_h = line_h * n
        widest = max((d.textlength(ln, font=f) for ln in lines), default=0)
        if block_h <= width_px * THICK and widest <= height_px * LEN:
            break
        size = int(size * 0.95)
        if size <= 8:
            break
    # Stack the lines ACROSS the strip thickness at their NATURAL spacing, from
    # the OUTER edge inwards. The strip is turned 180° when it sits on the right
    # edge, so canvas y=0 is the page-edge side either way: the first line borders
    # the text-edge distance, and the block runs towards the patches without ever
    # reaching them (the loop above already caps it at the strip width).
    #
    # Justifying the lines across the full thickness instead — the previous
    # behaviour — was wrong on both counts (Knut): it spread them to fill the
    # strip no matter how many there were, so deleting the blank lines between
    # them changed nothing on screen, and it pushed the last line's ink over the
    # inner edge into the patch area. Only the font SIZE may grow, until the
    # longest line hits the text-edge along the strip or the stack hits it across.
    line_h = size * 1.2
    block_h = line_h * n
    # The template caption keeps its centred block; clip text hugs the outer edge.
    start = (width_px - block_h) / 2 if valign == "top" else 0.0
    ys = [start + line_h * (i + 0.5) for i in range(n)]
    cx = (height_px * 0.04 if valign == "top" else height_px / 2)
    anchor = "lm" if valign == "top" else "mm"
    for ln, y in zip(lines, ys):
        try:
            d.text((cx, y), ln, font=f, fill=(0, 0, 0, 255), anchor=anchor)
        except Exception:  # pragma: no cover
            d.text((cx, y), ln, font=f, fill=(0, 0, 0, 255))
    return canvas.rotate(90, expand=True)


def _notes_sample_ctx() -> dict:
    """Placeholder values for the notes design when no real chart context is
    supplied (panel preview / template export)."""
    return {"count": "560", "instrument": "i1Pro", "paper": "A4 landscape",
            "page": "page 1/2", "strips": "12", "date": "2026-01-01",
            "project": "My printer profile"}


def _draw_wordmark_h(canvas: Image.Image, draw: "ImageDraw.ImageDraw",
                     x: float, top: float, height: float, max_w: float) -> float:
    """Draw the ChromIQ wordmark (serif "Chrom" + italic-magenta "IQ") left-
    anchored in a band of *height* at (x, top); returns the width consumed."""
    size = max(8, int(height * 0.74))
    f = _font(size, WORDMARK_FONT)
    for _ in range(24):
        f = _font(size, WORDMARK_FONT)
        f_iq = _font(size, WORDMARK_FONT, italic=True)
        iq_tile, iq_base, iq_left = _italic_tile(
            "IQ", f_iq, WORDMARK_IQ_RGB + (255,), shear=0.0)
        chrom_w = draw.textlength("Chrom", font=f)
        kern = size * 0.02
        total = chrom_w + kern + (iq_tile.width - iq_left)
        if total <= max_w and iq_tile.height <= height * 1.05:
            break
        size = int(size * 0.9)
        if size <= 8:
            break
    asc, desc = f.getmetrics()
    baseline = top + height * 0.5 + (asc - desc) / 2
    try:
        draw.text((x, baseline), "Chrom", font=f, fill=WORDMARK_RGB, anchor="ls")
        canvas.paste(iq_tile,
                     (int(x + chrom_w + kern - iq_left), int(baseline - iq_base)),
                     iq_tile)
    except Exception:  # pragma: no cover - default font without anchor
        draw.text((x, top), "ChromIQ", font=f, fill=WORDMARK_RGB)
    return chrom_w + kern + (iq_tile.width - iq_left)


def _notes_row(draw: "ImageDraw.ImageDraw", font, y_center: float, x0: float,
               x_end: float, segments: list, mm2px: float,
               rule_rgb=(120, 120, 120)) -> None:
    """Lay out one info row left→right. *segments* are ``("text", s)`` for a
    filled value or ``("rule", label)`` for a handwrite label followed by a write
    line. The spare length is split among the rules, so a longer strip (taller
    page) gives the user more room to write — not just a stretched bitmap."""
    gap = max(2, round(3.0 * mm2px))
    label_gap = max(1, round(1.5 * mm2px))
    fixed = 0.0
    n_rules = 0
    for kind, s in segments:
        fixed += draw.textlength(s, font=font) + gap
        if kind == "rule":
            n_rules += 1
            fixed += label_gap
    rule_w = max(0.0, (x_end - x0) - fixed) / n_rules if n_rules else 0.0
    asc, desc = font.getmetrics()
    baseline = y_center + (asc - desc) / 2
    lw = max(1, round(0.3 * mm2px))
    x = x0
    for kind, s in segments:
        draw.text((x, baseline), s, font=font, fill=(0, 0, 0), anchor="ls")
        x += draw.textlength(s, font=font)
        if kind == "rule":
            x += label_gap
            ly = baseline + max(1, round(0.6 * mm2px))
            draw.line([(x, ly), (x + rule_w, ly)], fill=rule_rgb, width=lw)
            x += rule_w
        x += gap


def _render_notes_strip(width_px: int, height_px: int, dpi: int,
                        ctx: dict | None, font_family: str) -> Image.Image:
    """The ChromIQ clip-border notes design (#93): a spectrum accent bar, the
    wordmark, and three info rows — auto-filled values plus handwrite rules.

    Drawn on a horizontal length×thickness canvas (so it scales by *content*, not
    by stretching) and rotated 90° to read up the strip. Font size follows the
    clip-border thickness; the handwrite rules absorb the extra length."""
    c = dict(_notes_sample_ctx())
    if ctx:
        c.update({k: str(v) for k, v in ctx.items() if v not in (None, "")})
    mm2px = dpi / 25.4
    L, T = max(1, height_px), max(1, width_px)         # length × thickness (px)
    canvas = Image.new("RGB", (L, T), (255, 255, 255))
    d = ImageDraw.Draw(canvas)
    pad = max(2, round(2.0 * mm2px))

    # Full-length spectrum accent bar along the top edge.
    bar_h = max(2, round(0.06 * T))
    seg = L / len(ACCENT_RGB)
    for i, col in enumerate(ACCENT_RGB):
        d.rectangle([round(i * seg), 0, round((i + 1) * seg) - 1, bar_h - 1], fill=col)

    top = bar_h + pad
    avail = max(1.0, T - top - pad)
    row_h = avail / 3.0

    logo_w = _draw_wordmark_h(canvas, d, pad, top, avail, max_w=L * 0.20)
    x0 = pad + logo_w + max(round(6 * mm2px), pad * 2)
    x_end = L - pad
    avail_w = max(1.0, x_end - x0)
    yc = [top + row_h * (i + 0.5) for i in range(3)]

    # Row content. Rules ("rule") absorb spare length; texts are fixed-width.
    left1 = (f"{c['count']} patches  ·  {c['instrument']}  ·  {c['paper']}  ·  "
             f"colour management: OFF")
    right1 = f"{c['page']}  ·  strips on page: {c['strips']}"
    row2 = [("text", f"date: {c['date']}"), ("rule", "printer:"),
            ("rule", "ink set:"), ("rule", "paper brand / type:")]
    row3 = [("rule", "media / resolution setting:"),
            ("text", f"profile name: {c['project']}")]

    # Font: sized from the clip thickness for legibility, then shrunk so the
    # busiest row still fits the length (keeping a minimum write-line per rule),
    # so a wider clip means bigger text — never text running off the strip (#93).
    gap = max(2, round(3.0 * mm2px))
    min_line = round(12.0 * mm2px)

    def _need(font) -> float:
        n1 = d.textlength(left1, font=font) + gap + d.textlength(right1, font=font)
        n2 = sum(d.textlength(s, font=font) + gap for _, s in row2) \
            + 3 * min_line
        n3 = sum(d.textlength(s, font=font) + gap for _, s in row3) + min_line
        return max(n1, n2, n3)

    size = max(8, int(row_h * 0.46))
    font = _font(size, font_family)
    need = _need(font)
    if need > avail_w:
        size = max(8, int(size * avail_w / need))
        font = _font(size, font_family)
    asc, desc = font.getmetrics()

    b1 = yc[0] + (asc - desc) / 2
    d.text((x0, b1), left1, font=font, fill=(0, 0, 0), anchor="ls")
    d.text((x_end, b1), right1, font=font, fill=(90, 90, 90), anchor="rs")
    _notes_row(d, font, yc[1], x0, x_end, row2, mm2px)
    _notes_row(d, font, yc[2], x0, x_end, row3, mm2px)

    return canvas.rotate(90, expand=True)


@dataclass(frozen=True)
class RenderResult:
    images: list[Image.Image]
    low_contrast_passes: list[int]   # global pass indices flagged by the guard
    # Bottom of the rendered strip-label band (labels + underline) in page px,
    # or None when indicators are off. The measure-tab scan arrow hangs from
    # this line, printtarg-style; without it the arrow floats above the patches.
    label_band_bottom_px: int | None = None
    # Per-page patch geometry with exact device values, populated only when
    # ``collect_device_geom`` is set (non-RGB targets → Tier D device-native
    # raster). Each entry is ``("rect", (x0, y0, xR, yB), device_tuple)`` or
    # ``("hex", [points], device_tuple)`` — the exact ink coverage of every
    # measured patch, independent of the display-RGB preview.
    patch_geom: list[list[tuple]] | None = None


def _hexagon_points(x0: int, y0: int, w: int, ph: int, step: int):
    """Six vertices of a printtarg-style SpectroScan hexagon for the patch slot
    at ``(x0, y0)`` sized ``w × ph`` (px), staggered ±¼·w by the patch's index
    in the strip (#93, Knut). Pointed top and bottom, flat vertical sides; the
    apexes reach ⅙·ph beyond the slot top and bottom (the geometry reserves that
    as ``hxeh``), so neighbouring rows interlock as in ``printtarg -h``."""
    dx = round(-w / 4) if step % 2 == 0 else round(w / 4)
    t6 = ph / 6.0
    left, right = x0 + dx, x0 + w + dx
    cx = round(x0 + w / 2 + dx)
    return [
        (cx, round(y0 - t6)),               # top apex
        (right, round(y0 + t6)),            # upper-right
        (right, round(y0 + 5 * t6)),        # lower-right
        (cx, round(y0 + ph + t6)),          # bottom apex
        (left, round(y0 + 5 * t6)),         # lower-left
        (left, round(y0 + t6)),             # upper-left
    ]


def _fill_rect(draw: "ImageDraw.ImageDraw", box, fill) -> bool:
    """Draw a filled rectangle, skipping a degenerate (inverted / zero-area) box.

    Integer rounding of a sub-pixel patch, spacer or furniture dimension can
    momentarily invert an edge (``x1 < x0`` or ``y1 < y0``) — Pillow then raises
    "y1 must be greater than or equal to y0" and aborts the entire page, which
    surfaced as a hard error when applying a dense multi-ink chart (#125). Such a
    rectangle covers no pixels, so it is safe to skip. Returns ``True`` when a
    rectangle was actually drawn, so callers can gate the matching
    device-geometry row on the same condition (keeping the raster, device-TIFF
    and vector-PDF outputs consistent). The device raster already guards the same
    way in :func:`build_device_pages`."""
    x0, y0, x1, y1 = box
    if x1 < x0 or y1 < y0:
        return False
    draw.rectangle([x0, y0, x1, y1], fill=fill)
    return True


def render_pages(
    target: ColorTarget,
    layout: Layout,
    geom: Geom,
    *,
    seed: int,
    randomize: bool = True,
    paper_w_mm: float,
    paper_h_mm: float,
    dpi: int = 300,
    strip_pattern: str = permutation.DEFAULT_STRIP_PATTERN,
    patch_pattern: str = permutation.DEFAULT_PATCH_PATTERN,
    spacer_mode: str = "colored",
    spacer_palette: "list[tuple[int, int, int]] | None" = None,
    spacer_overrides: "dict[int, tuple[int, int, int]] | None" = None,
    edge_spacers: bool = False,
    draw_indicators: bool = True,
    indicator_font: str = DEFAULT_INDICATOR_FONT,
    indicator_size_mm: float = 0.0,
    indicator_bold: bool = False,
    indicator_italic: bool = False,
    indicator_rotation: int = 0,
    indicator_align: str = "left",
    underline_mode: str = "off",
    underline_thickness_mm: float = 0.5,
    underline_gap_mm: float = 0.5,
    chart_text: str = "",
    chart_text_font: str = "Inter",
    chart_text_size_mm: float = 0.0,
    chart_text_bold: bool = False,
    chart_text_italic: bool = False,
    stamp_text: str = "",
    text_edge_mm: float = TEXT_EDGE_MARGIN_MM,
    clip_content_mode: str = "off",
    clip_text: str = "",
    clip_text_font: str = "Inter",
    clip_text_size_mm: float = 0.0,
    clip_image_path: str = "",
    clip_image_rotation: int = 0,
    clip_image_scale: float = 100.0,
    clip_image_offset_x_mm: float = 0.0,
    clip_image_offset_y_mm: float = 0.0,
    clip_flip_180: bool = False,
    strip_label_offset_mm: float = 0.0,
    text_ctx: "dict | None" = None,
    helper_markers: bool = False,
    helper_marker_edge_mm: float = 2.0,
    helper_marker_len_mm: float = 2.0,
    helper_marker_per_patch: int = 3,
    helper_markers_top_bottom: bool = True,
    helper_markers_sides: bool = True,
    collect_device_geom: bool = False,
) -> RenderResult:
    """Render one :class:`PIL.Image` per page for *target*.

    *spacer_mode* picks the inter-patch spacer colour: ``"colored"`` (default,
    like printtarg) or ``"bw"``.  No spacers are drawn when the geometry has no
    gap (``spacer_mode`` ``"none"`` ⇒ build with ``spacer_on=False``).
    """
    mm2px = dpi / 25.4
    W = max(1, round(paper_w_mm * mm2px))
    H = max(1, round(paper_h_mm * mm2px))

    # Patch list incl. padding, then slot assignment (identical to ti2_writer).
    media = target.media_patch()
    patches = list(target.patches) + [media] * layout.padding
    total = len(patches)
    slots = permutation.location_permutation(total, seed, randomize)
    rgb_by_slot: list[tuple[int, int, int]] = [(255, 255, 255)] * total
    # Device values by slot mirror the RGB fills, so Tier D can paint the exact
    # ink coverage of each patch into the separated raster (the RGB preview is a
    # display approximation; these values are what chartread measures).
    dev_by_slot: list[tuple[float, ...]] = [(0.0,) * target.n_channels] * total
    for i, (dev, _xyz) in enumerate(patches):
        rgb_by_slot[slots[i]] = to_display_rgb(dev, target.color_rep)
        dev_by_slot[slots[i]] = dev

    place = geometry.placement(geom, paper_w_mm, paper_h_mm, layout)
    steps = layout.steps_in_pass
    pppage = layout.patches_per_page
    label_strip = permutation.make_labeller(strip_pattern)
    # THE USER'S PATTERN, NOT THE DEFAULT ONE. The row band exists so that a
    # patch's place on paper can be found again in the file, and it was drawn
    # with the built-in pattern whatever the chart was made with: a chart set
    # to "A-Z;1-999" printed rows 1, 2, 3 while its own .ti2 -- and therefore
    # the .ti3 and the report -- called those same rows A, B, C. The label on
    # the sheet disagreed with the measurement, which defeats the only thing
    # the band is for. Reported from beta 5.
    label_patch = permutation.make_labeller(patch_pattern)

    def px(mm: float) -> int:
        return round(mm * mm2px)

    pl_px = px(place.plen)
    sp_px = px(place.pspa)
    # Hexagonal patches (printtarg -h on the SpectroScan; the shape option on a
    # CR30, #159): draw interlocking hexagons instead of rectangles (#93, Knut).
    # Capacity is unchanged — only the shape.
    from .instruments import is_hexagonal as _is_hex
    ss_hex = _is_hex(geom)
    # Row-number band width (SpectroScan labels the grid 2-D): 0 for instruments
    # without it. Drawn to the left of the patches, the band placement reserves.
    _row_band_px = px(getattr(geom, "rlwi", 0.0))
    ind_px = px(effective_indicator_size_mm(
        geom, dpi, indicator_font, indicator_size_mm))
    font = _font(ind_px, indicator_font, indicator_bold, indicator_italic)
    # Vector-PDF furniture: the exact font file + variable instance + PIL ascent,
    # so a collected text run places identically to what Pillow drew (#72).
    _ind_font_file, _ind_var = _font_file_and_variation(
        indicator_font, indicator_bold, indicator_italic)
    try:
        _ind_ascent, _ind_descent = font.getmetrics()
    except Exception:
        _ind_ascent, _ind_descent = ind_px, ind_px // 4

    def _collect_rotated_label(cx: int, y_top: int, off: int, text: str,
                               tile: "Image.Image", degrees: int) -> None:
        """Collect a rotated strip label as a rotated vector run. The engine lays
        the letters in an un-rotated tile, rotates it CCW and pastes it centred;
        for the 0/90/180/270 cases the tile's baseline-left anchor maps to an
        exact pixel, so the run reproduces it (rotation about that anchor)."""
        if not (collect_device_geom and _ind_font_file and text):
            return
        widths = [draw.textlength(ch, font=font) for ch in text]
        wc = int(sum(widths) + _spc * (len(text) - 1)) + 4     # un-rotated tile W
        hc = _ind_ascent + _ind_descent + 4                    # un-rotated tile H
        ax, ay = 2, 2 + _ind_ascent                            # baseline-left in tile
        d = degrees % 360
        if d == 90:
            adx, ady = ay, wc - 1 - ax
        elif d == 270:
            adx, ady = hc - 1 - ay, ax
        else:                                                  # 180
            adx, ady = wc - 1 - ax, hc - 1 - ay
        px_paste = cx - tile.width // 2
        py_paste = y_top + off
        _geom_rows.append(("text", px_paste + adx, py_paste + ady, text,
                           _ind_font_file, ind_px, _spc if len(text) > 1 else 0,
                           d, (0, 0, 0), _ind_var))

    def _collect_label(cx: int, top: int, text: str) -> None:
        """Collect a centred strip label as a vector text run at the exact left/
        baseline Pillow uses (single letter → centred on advance; multi → spaced)."""
        if not (collect_device_geom and _ind_font_file and text):
            return
        widths = [draw.textlength(ch, font=font) for ch in text]
        if len(text) > 1 and _spc > 0:
            total = sum(widths) + _spc * (len(text) - 1)
        else:
            total = widths[0] if widths else 0.0
        left = cx - total / 2.0
        _geom_rows.append(("text", left, top + _ind_ascent, text, _ind_font_file,
                           ind_px, _spc if len(text) > 1 else 0, 0, (0, 0, 0),
                           _ind_var))
    if underline_mode == "colored":          # legacy alias → 5-segment bar
        underline_mode = "segments"
    underline_on = draw_indicators and underline_mode in ("segments", "cycle", "black")
    ul_th = max(1, px(underline_thickness_mm or 0.5))
    ul_gap = px(underline_gap_mm)

    # Inter-letter gap (constant for the whole chart) and the vertical height the
    # label band reserves. For side-rotated labels (90°/270°) the band is sized
    # to the LONGEST label on the chart so every strip's reading-start letter can
    # be anchored on the same line (the patch-side line stays fixed regardless of
    # how many letters a label has) and the underline clears the tallest label.
    _spc = max(1, round(ind_px * INDICATOR_LETTER_SPACING))
    _rot = indicator_rotation % 360
    _is_side = _rot in (90, 270)
    if draw_indicators and _is_side:
        _n_total_strips = max(1, (total + steps - 1) // steps)
        _longest = label_strip(_n_total_strips)
        label_band_h = _indicator_tile(_longest, font, _spc, _rot).height
    else:
        label_band_h = ind_px

    # Strip-label vertical position: leader_top is where the band sits; a user
    # offset (mm) nudges the labels up (negative, toward the top margin) or down,
    # together with their underline (#93).
    _lbl_top = px(place.leader_top + strip_label_offset_mm)
    _band_bottom = None
    if draw_indicators:
        _band_bottom = _lbl_top + label_band_h + \
            ((ul_gap + ul_th) if underline_on else 0)

    def _resolve_with(t: str, ctx: dict) -> str:
        try:
            return t.format(**ctx) if t else ""
        except (KeyError, IndexError, ValueError):
            return t                       # leave unknown placeholders literal

    images: list[Image.Image] = []
    page_geoms: list[list[tuple]] = []
    for page in range(layout.pages):
        img = Image.new("RGB", (W, H), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        _geom_rows: list[tuple] = []
        # Per-page placeholder context: {page} = "page X/Y", plus the chart-wide
        # {project}/{paper}/… from text_ctx. Used for chart text + clip text.
        _pctx = dict(text_ctx or {})
        _pctx["page"] = f"page {page + 1}/{layout.pages}"
        _chart_text = _resolve_with(chart_text, _pctx)
        _clip_text = _resolve_with(clip_text, _pctx)
        first = page * pppage
        last = min(total, first + pppage)
        n_on_page = last - first
        n_passes = (n_on_page + steps - 1) // steps

        for p in range(n_passes):
            x0 = px(place.x_of(p))
            # Right edge from the patch's true mm position, not x0 + a fixed
            # rounded width: when strips touch (pwid == rrsp) the 8 mm pitch
            # rounds alternately to 94/95 px, so a fixed 94 px width left a 1 px
            # gap after every other strip. Deriving xR here tiles them seamlessly
            # while still leaving any intended gap when pwid < rrsp.
            xR = px(place.x_of(p) + place.pwid)
            strip_w = xR - x0
            global_strip = (first // steps) + p
            # ColorMunki "offset every second strip": odd strips shift down by
            # the rig stagger (#93, Knut). 0 for everything else.
            _stag = px(getattr(geom, "row_stagger_mm", 0.0)) if (global_strip & 1) else 0
            col_slots = list(range(first + p * steps,
                                   min(last, first + (p + 1) * steps)))
            if draw_indicators:
                _lbl = label_strip(global_strip + 1)
                _cx = x0 + strip_w // 2          # centre over the strip
                _y = _lbl_top
                if _rot == 0:
                    _draw_indicator(draw, _cx, _y, _lbl, font, _spc)
                    _collect_label(_cx, _y, _lbl)
                else:                            # rotated label → tile + paste
                    _tile = _indicator_tile(_lbl, font, _spc, indicator_rotation)
                    # Justify within the label band along the reading axis. The
                    # patch-side line (band bottom) is fixed for every strip, so a
                    # label gaining a second letter grows AWAY from the patches
                    # instead of creeping toward them (#93).
                    _extra = max(0, label_band_h - _tile.height)
                    if not _is_side:             # 180°: top-aligned like before
                        _off = 0
                    elif indicator_align == "center":
                        _off = _extra // 2
                    elif indicator_align == "left":   # reading-start anchored
                        _off = _extra if _rot == 90 else 0
                    else:                             # right: reading-end anchored
                        _off = 0 if _rot == 90 else _extra
                    img.paste(_tile, (_cx - _tile.width // 2, _y + _off), _tile)
                    _collect_rotated_label(_cx, _y, _off, _lbl, _tile,
                                           indicator_rotation)
                if underline_on and underline_mode == "cycle":   # one accent / strip
                    _ly = _y + label_band_h + ul_gap
                    _acc = ACCENT_RGB[global_strip % len(ACCENT_RGB)]
                    if _fill_rect(draw, [x0, _ly, xR - 1, _ly + ul_th - 1], _acc) \
                            and collect_device_geom:
                        _geom_rows.append(
                            ("vrect", (x0, _ly, xR - 1, _ly + ul_th - 1), _acc))
                # SpectroScan labels the grid 2-D: column letters on top (above)
                # plus row NUMBERS down the side, in the reserved rlwi band to the
                # left of the patches. Drawn once, against the leftmost strip (#93,
                # Knut). The band sits in [x0 - rlwi, x0].
            # ROW LABELS ARE NOT PART OF THE STRIP LABELS. This block used to sit
            # inside `if draw_indicators:`, so asking for row indicators with the
            # strip letters off printed nothing at all -- which is why the checkbox
            # was greyed out rather than fixed. On a CR30 or a SpectroScan the row
            # number is the useful half: the instrument is placed on ONE patch at a
            # time, and the strip letter is the part you can spare (Basti, 2026-09-01).
            if _row_band_px > 0 and p == 0:
                # Right-align each number so it ends just left of the patches
                # and grows LEFT into the band — a two-digit number (10–13…)
                # can't spill over the patches (#93, Knut). For hex patches the
                # left column's even rows stagger ¼·width LEFT past x0, so clear
                # that protrusion too, else the hexagons cover the numbers.
                _gap = max(1, px(1.0))
                _protrude = (strip_w // 4) if ss_hex else 0
                _rx = x0 - _protrude - _gap
                for _j in range(len(col_slots)):
                    _ry = (px(place.y_of(_j)) + px(place.y_of(_j) + place.plen)) // 2
                    _txt = label_patch(_j + 1)
                    _tw = int(draw.textlength(_txt, font=font))
                    # CLAMP AT THE PAPER EDGE. In area-first the row band is
                    # no longer reserved outside the margin (the margin is
                    # the law for the PATCHES), so with a small left margin
                    # these numbers grow left past x=0 and simply vanish off
                    # the sheet. Basti's ruling, 2026-08-30: clamp them at
                    # the edge and warn, the mirror of what the strip labels
                    # already do at the top. Furniture slides; patches do
                    # not move.
                    _tx = max(0, _rx - _tw)
                    draw.text((_tx, _ry - ind_px // 2), _txt,
                              font=font, fill=(0, 0, 0))
                    if collect_device_geom and _ind_font_file:
                        _geom_rows.append(
                            ("text", _tx, _ry - ind_px // 2 + _ind_ascent,
                             _txt, _ind_font_file, ind_px, 0, 0, (0, 0, 0),
                             _ind_var))
            for j, gslot in enumerate(col_slots):
                y0 = px(place.y_of(j)) + _stag
                # Derive each row's bottom edge from its true mm position (the
                # way xR does horizontally) instead of adding a fixed rounded
                # height: round(plen)+round(pspa) drifts from round(plen+pspa),
                # which left a 1 px gap between the spacer and the next patch on
                # every other row. Tying the spacer's bottom to the next patch's
                # top tiles them seamlessly (#93).
                yB = px(place.y_of(j) + place.plen) + _stag    # patch bottom edge
                rgb = rgb_by_slot[gslot]
                if ss_hex:
                    _pts = _hexagon_points(x0, y0, xR - x0, yB - y0, j)
                    draw.polygon(_pts, fill=rgb)
                    if collect_device_geom:
                        _geom_rows.append(("hex", _pts, dev_by_slot[gslot]))
                else:
                    if _fill_rect(draw, [x0, y0, xR - 1, yB - 1], rgb) \
                            and collect_device_geom:
                        _geom_rows.append(
                            ("rect", (x0, y0, xR, yB), dev_by_slot[gslot]))
                if sp_px > 0 and spacer_mode != "none" and j + 1 < len(col_slots):
                    y_next = px(place.y_of(j + 1)) + _stag     # next patch top
                    nxt = rgb_by_slot[col_slots[j + 1]]
                    # A per-spacer manual override (keyed by flat geometric index)
                    # wins over the auto/contrast colour.
                    _flat = global_strip * steps + j
                    _ov = spacer_overrides.get(_flat) if spacer_overrides else None
                    _fill = _ov if _ov is not None else contrast.spacer_for_mode(
                        spacer_mode, rgb, nxt, spacer_palette)
                    if _fill_rect(draw, [x0, yB, xR - 1, y_next - 1], _fill) \
                            and collect_device_geom:  # coloured spacer → device ink
                        _geom_rows.append(
                            ("spacer", (x0, yB, xR, y_next), _fill))
            # Bracket the strip with a leading + trailing spacer (printtarg does
            # this). Fits in space the layout already reserves, so it doesn't
            # change the patch count. Auto-coloured against the paper white on the
            # outer side and the adjacent patch on the inner; not individually
            # recolourable (the override scheme covers the between-patch spacers).
            # SPACER MODE "none" MEANS BARE PAPER, NOT A BLACK BAR.
            # Asking for a gap without a spacer used to draw one anyway,
            # because the colour chooser falls back to its black/white rule for
            # any mode it does not recognise — so a chart set to "none" with a
            # 2.5 mm gap came out banded (Sebastian, 2026-08-13). Skipping the
            # fill leaves the gap the colour of the sheet, which is what the
            # setting says. The geometry is unchanged, so patch positions,
            # capacity and every recorded box stay exactly as they were.
            if edge_spacers and sp_px > 0 and spacer_mode != "none" and col_slots:
                _white = (255, 255, 255)
                _first = rgb_by_slot[col_slots[0]]
                _last = rgb_by_slot[col_slots[-1]]
                _yl = px(place.y_of(0)) + _stag - sp_px     # leading: above patch 0
                _lead = contrast.spacer_for_mode(spacer_mode, _white, _first,
                                                 spacer_palette)
                _lead_ok = _fill_rect(draw, [x0, _yl, xR - 1, _yl + sp_px - 1], _lead)
                _yt = px(place.y_of(len(col_slots) - 1) + place.plen) + _stag  # trailing
                _trail = contrast.spacer_for_mode(spacer_mode, _last, _white,
                                                  spacer_palette)
                _trail_ok = _fill_rect(draw, [x0, _yt, xR - 1, _yt + sp_px - 1], _trail)
                if collect_device_geom:
                    if _lead_ok:
                        _geom_rows.append(("spacer", (x0, _yl, xR, _yl + sp_px), _lead))
                    if _trail_ok:
                        _geom_rows.append(("spacer", (x0, _yt, xR, _yt + sp_px), _trail))
        # Full-width rule under the whole label row (one continuous line):
        # "segments" splits it into the five accents across the entire width;
        # "black" is a single plain line. ("cycle" is drawn per strip above.)
        if (draw_indicators and underline_mode in ("segments", "black")
                and n_passes > 0):
            _ly = _lbl_top + label_band_h + ul_gap
            _yb = _ly + ul_th - 1
            x_left = px(place.x_of(0))
            x_right = px(place.x_of(n_passes - 1) + place.pwid) - 1
            if underline_mode == "black":
                if _fill_rect(draw, [x_left, _ly, x_right, _yb], (0, 0, 0)) \
                        and collect_device_geom:
                    _geom_rows.append(("vrect", (x_left, _ly, x_right, _yb), (0, 0, 0)))
            else:                                     # 5 equal segments full-width
                _span = x_right - x_left + 1
                _n = len(ACCENT_RGB)
                for _k in range(_n):
                    _sx0 = x_left + round(_span * _k / _n)
                    _sx1 = x_left + round(_span * (_k + 1) / _n) - 1
                    if _fill_rect(draw, [_sx0, _ly, _sx1, _yb], ACCENT_RGB[_k]) \
                            and collect_device_geom:
                        _geom_rows.append(
                            ("vrect", (_sx0, _ly, _sx1, _yb), ACCENT_RGB[_k]))

        # Left clip-strip content (i1/p3): rendered natively into the reserved
        # lbord band, since the engine knows its exact geometry.
        if clip_content_mode != "off":
            _area = geometry.clip_area_px(geom, paper_h_mm, dpi, paper_w_mm)
            if _area is not None and _area[2] > 0 and _area[3] > 0:
                _ax, _ay, _aw, _ah = _area
                _notes_ctx = dict(_pctx)
                _notes_ctx["count"] = str(layout.total_patches)
                _notes_ctx["strips"] = str(n_passes)
                _clip = render_clip_strip(
                    clip_content_mode, width_px=_aw, height_px=_ah, dpi=dpi,
                    text=_clip_text, font_family=clip_text_font,
                    text_size_mm=clip_text_size_mm,
                    image_path=clip_image_path, ctx=_notes_ctx,
                    image_rotation=clip_image_rotation,
                    image_scale=clip_image_scale,
                    image_offset_x_mm=clip_image_offset_x_mm,
                    image_offset_y_mm=clip_image_offset_y_mm)
                # On the right edge the band sits on the far side of the sheet, so
                # turn the content 180° to keep it the right way up for the reader
                # (Knut, #93). The user can override with clip_flip_180 (XOR), e.g.
                # to make a right-side clip read the same direction as the bottom
                # stamp. Left clips are upright by default; flip turns them over.
                _flip = (getattr(geom, "clip_side", "left") == "right") ^ bool(clip_flip_180)
                if _flip:
                    _clip = _clip.rotate(180, expand=True)
                img.paste(_clip, (_ax, _ay))
                if collect_device_geom:      # colour the notes strip in device ink
                    _geom_rows.append(
                        ("clip", (_ax, _ay), np.asarray(_clip.convert("RGB"))))

        # Bottom-of-sheet text: custom chart text + optional command stamp,
        # drawn in the bottom margin (clear of the patches).
        _btxt = [t for t in (_chart_text, stamp_text) if t]
        if _btxt:
            _sfont_px = px(chart_text_size_mm or 3.2)
            sfont = _font(_sfont_px, chart_text_font,
                          chart_text_bold, chart_text_italic)
            _sfile, _svar = _font_file_and_variation(
                chart_text_font, chart_text_bold, chart_text_italic)
            try:
                _sasc = sfont.getmetrics()[0]
            except Exception:
                _sasc = _sfont_px
            line_h = px(4.2)
            yy = H - px(text_edge_mm) - line_h * len(_btxt)
            for ln in _btxt:
                draw.text((px(geom.margin_l), yy), ln, font=sfont, fill=(0, 0, 0))
                if collect_device_geom and _sfile:
                    _geom_rows.append(("text", px(geom.margin_l), yy + _sasc, ln,
                                       _sfile, _sfont_px, 0, 0, (0, 0, 0), _svar))
                yy += line_h
        # Ruler helper markers (#152, Knut). Drawn LAST so nothing already on
        # the page can cover them, and on every page — they help while reading
        # any sheet of any chart type. Overlapping other furniture is allowed;
        # the help text tells the user to adjust the distances if it bothers
        # them, which was his ruling rather than an omission.
        if helper_markers:
            try:
                for (mx0, my0, mx1, my1) in geometry.helper_marker_lines_mm(
                        geom, paper_w_mm, paper_h_mm, layout,
                        edge_mm=helper_marker_edge_mm,
                        length_mm=helper_marker_len_mm,
                        per_patch=helper_marker_per_patch,
                        top_bottom=helper_markers_top_bottom,
                        sides=helper_markers_sides):
                    _w = max(1, px(_HELPER_MARKER_W_MM))
                    draw.line((px(mx0), px(my0), px(mx1), px(my1)),
                              fill=(0, 0, 0), width=_w)
                    if collect_device_geom:
                        # THE VECTOR PDF GETS THEM TOO. Every other element on
                        # the sheet appends to the display list; the markers did
                        # not, so "Also export a PDF" silently produced a chart
                        # with no dashes on it while the TIFF had them. A dash is
                        # a thin filled rule, which is exactly what the `vrect`
                        # element already is.
                        #
                        # The rectangle is the one PIL actually inks, measured
                        # rather than assumed: a width-w line covers rows
                        # ``y - (w-1)//2`` through ``y + w//2`` INCLUSIVE — so it
                        # is not centred on y for an even width — and runs from
                        # x0 to x1 inclusive. Taking it as centred put the PDF
                        # rule half a pixel above the TIFF dash and made it one
                        # pixel short.
                        _lo, _hi = (_w - 1) // 2, _w // 2 + 1
                        _x0, _x1 = sorted((px(mx0), px(mx1)))
                        _y0, _y1 = sorted((px(my0), px(my1)))
                        if my0 == my1:                     # horizontal dash
                            _rect = (_x0, _y0 - _lo, _x1 + 1, _y1 + _hi)
                        else:                              # vertical dash
                            _rect = (_x0 - _lo, _y0, _x1 + _hi, _y1 + 1)
                        _geom_rows.append(("vrect", _rect, (0, 0, 0)))
            except Exception:      # noqa: BLE001 — never lose a chart to a marker
                log.warning("could not draw the helper markers", exc_info=True)
        images.append(img)
        page_geoms.append(_geom_rows)

    flagged = contrast.low_contrast_passes(rgb_by_slot, steps)
    return RenderResult(images=images, low_contrast_passes=flagged,
                        label_band_bottom_px=_band_bottom,
                        patch_geom=page_geoms if collect_device_geom else None)


def export_clip_template(out_base: str | Path, *, width_px: int, height_px: int,
                         width_mm: float, height_mm: float, dpi: int,
                         content: "Image.Image | None" = None) -> list[Path]:
    """Write the clip strip at its exact size, as ``.png`` and ``.pdf``.

    With *content* — the strip as the preview draws it — this is a proof of what
    will be printed, at the real size, for any content option. Knut, #164:
    *"The resulting files had ONLY the text for the Clip area field, and not the
    actual text/image shown in preview … The export Template should work on any
    of the Content options."*

    Without it (the band is switched off) the file is what it has always been: a
    BLANK canvas at the exact clip size, with a faint border, corner ticks and a
    dimension caption, to design a graphic in another tool and import back at a
    perfect fit. The guide marks and the caption are only drawn on that blank
    canvas — printed over real artwork they would have to be erased again.

    Returns the written paths.
    """
    # `out_base` is a base NAME the user typed in a save dialog, not a
    # filename — "clip-w10.0mm" has no extension to strip, and with_suffix("")
    # would eat ".0mm". See core/stem_paths.py.
    base = Path(out_base)
    mm2px = dpi / 25.4
    if content is not None:
        img = content.convert("RGB")
        if img.size != (max(1, width_px), max(1, height_px)):
            img = img.resize((max(1, width_px), max(1, height_px)))
        out: list[Path] = []
        png = artefact(base, ".png")
        img.save(str(png), dpi=(dpi, dpi))
        out.append(png)
        pdf = artefact(base, ".pdf")
        img.save(str(pdf), "PDF", resolution=float(dpi))
        out.append(pdf)
        return out
    img = Image.new("RGB", (max(1, width_px), max(1, height_px)), (255, 255, 255))
    d = ImageDraw.Draw(img)
    guide = (200, 200, 200)
    d.rectangle([0, 0, width_px - 1, height_px - 1], outline=guide, width=1)
    tick = max(3, round(3 * mm2px))               # corner crop ticks
    for cx, cy in ((0, 0), (width_px - 1, 0), (0, height_px - 1),
                   (width_px - 1, height_px - 1)):
        d.line([(cx, cy), (cx + (tick if cx == 0 else -tick), cy)], fill=guide, width=2)
        d.line([(cx, cy), (cx, cy + (tick if cy == 0 else -tick))], fill=guide, width=2)
    cap = f"{width_mm:.0f} × {height_mm:.0f} mm @ {dpi} dpi"
    overlay = _vtext(cap, "Inter", width_px, height_px, valign="top")
    img.paste(overlay, (0, 0), overlay)
    out: list[Path] = []
    png = base.with_suffix(".png")
    img.save(str(png), dpi=(dpi, dpi))
    out.append(png)
    pdf = base.with_suffix(".pdf")
    img.save(str(pdf), "PDF", resolution=float(dpi))  # px/dpi → exact physical mm
    out.append(pdf)
    return out


# Device colorant char (the suffix of a ``.ti1`` device field, e.g. CMYKOG_O →
# "O") → human ink name for the TIFF ``InkNames`` tag. Covers CMYK and the
# common extra/light inks; unknown codes fall back to a title-cased suffix.
_INK_SUFFIX_NAMES = {
    "C": "Cyan", "M": "Magenta", "Y": "Yellow", "K": "Black",
    "O": "Orange", "G": "Green", "R": "Red", "B": "Blue", "V": "Violet",
    "W": "White", "LC": "Light Cyan", "LM": "Light Magenta",
    "LK": "Light Black", "LY": "Light Yellow", "LLK": "Light Light Black",
    "MC": "Light Cyan 2", "MM": "Light Magenta 2",
}


def ink_names_from_fields(device_fields: list[str]) -> list[str]:
    """Human ink names (for the TIFF ``InkNames`` tag) from ``.ti1`` device fields."""
    out: list[str] = []
    for f in device_fields:
        suf = f.split("_")[-1].upper()
        out.append(_INK_SUFFIX_NAMES.get(suf, suf.title()))
    return out


def _k_channel_index(device_fields: list[str]) -> int | None:
    """Index of the black (K) channel, or ``None`` if the ink set has none."""
    for i, f in enumerate(device_fields):
        if f.split("_")[-1].upper() == "K":
            return i
    return None


def build_device_pages(result: RenderResult, target, *, bit16: bool = False
                       ) -> list[np.ndarray]:
    """Turn a collected render into per-page device-native ``(H, W, n)`` rasters.

    Every measured patch is painted with its **exact** ink coverage (0–100 % →
    0..max), so what a RIP prints is bit-exact to what chartread expects — the
    same exactness-by-construction the RGB path has. All page furniture (strip
    labels, indicators, underlines, spacers, chart text, notes/clip strip) is
    folded into the **black-ink** channel from the preview's darkness outside the
    patch areas, keeping the sheet navigable without touching any patch value.
    """
    if result.patch_geom is None:
        raise ValueError("render lacked collect_device_geom=True; no device geometry")
    n = target.n_channels
    k_idx = _k_channel_index(target.device_fields)
    maxval = 65535 if bit16 else 255
    dtype = np.uint16 if bit16 else np.uint8
    arrays: list[np.ndarray] = []
    for img, rows in zip(result.images, result.patch_geom):
        W, H = img.size
        dev = np.zeros((H, W, n), dtype=np.float32)
        occ = np.zeros((H, W), dtype=bool)          # measured-patch pixels
        for elem in rows:
            kind = elem[0]
            # Vector-PDF-only furniture (text runs, underline rules) is already
            # drawn on the preview and folded into K by luminance below; the
            # device raster ignores it here.
            if kind in ("text", "vrect"):
                continue
            coord, values = elem[1], elem[2]
            if kind == "clip":
                # Notes/clip strip: carry its rendered artwork into device ink so
                # a coloured logo/header prints in colour (approx.), black text
                # stays crisp K. Unmeasured furniture in a reserved band.
                ax, ay = coord
                sub = values
                sh, sw = sub.shape[:2]
                x1, y1 = min(W, ax + sw), min(H, ay + sh)
                ax0, ay0 = max(0, ax), max(0, ay)
                if x1 > ax0 and y1 > ay0:
                    conv = to_device_approx_array(
                        sub[ay0 - ay:y1 - ay, ax0 - ax:x1 - ax], target.device_fields)
                    dev[ay0:y1, ax0:x1, :] = conv
                    occ[ay0:y1, ax0:x1] = True
                continue
            if kind == "spacer":
                # Coloured contrast spacer: carry its display colour into device
                # ink (unmeasured furniture, so an approximation is fine) instead
                # of flattening it to black — matching printtarg's coloured
                # spacers. Painted like a rect and excluded from the K fold-in.
                vals = np.asarray(
                    to_device_approx(values, target.device_fields), dtype=np.float32)
                x0, y0, xR, yB = coord
                x0, y0 = max(0, x0), max(0, y0)
                xR, yB = min(W, xR), min(H, yB)
                if xR > x0 and yB > y0:
                    dev[y0:yB, x0:xR, :] = vals
                    occ[y0:yB, x0:xR] = True
                continue
            vals = np.asarray(values, dtype=np.float32)
            if len(vals) != n:                       # defensive: pad/trim
                vals = np.resize(vals, n)
            if kind == "rect":
                x0, y0, xR, yB = coord
                x0, y0 = max(0, x0), max(0, y0)
                xR, yB = min(W, xR), min(H, yB)
                if xR <= x0 or yB <= y0:
                    continue
                dev[y0:yB, x0:xR, :] = vals
                occ[y0:yB, x0:xR] = True
            else:                                    # "hex": polygon mask
                mask = Image.new("L", (W, H), 0)
                ImageDraw.Draw(mask).polygon(coord, fill=255)
                m = np.asarray(mask, dtype=bool)
                dev[m] = vals
                occ |= m
        rgb = np.asarray(img, dtype=np.float32)
        lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
        furniture_k = (255.0 - lum) * (100.0 / 255.0)
        furniture_k[occ] = 0.0                        # never overwrite a patch
        if k_idx is not None:
            dev[..., k_idx] = np.maximum(dev[..., k_idx], furniture_k)
        else:                                         # no K: rich composite black
            for c in range(n):
                dev[..., c] = np.maximum(dev[..., c], furniture_k)
        arrays.append(np.clip(dev * (maxval / 100.0) + 0.5, 0, maxval).astype(dtype))
    return arrays


def save_separated_tiffs(arrays: list[np.ndarray], base_path: str | Path,
                         dpi: int = 300, *, ink_names: list[str],
                         compression: str = "lzw") -> list[Path]:
    """Write device-native ``(H, W, n)`` arrays as ``photometric='separated'``
    TIFF(s) with an ``InkNames`` tag, so a RIP knows exactly which ink each
    channel drives. CMYK writes ``InkSet=1``; extra-ink sets write ``InkSet=2``
    with the surplus samples flagged unspecified. Single page → ``base.tif``;
    multiple → ``base_NN.tif``.
    """
    base = Path(base_path)
    stem = base.with_suffix("")
    res = dpi / 2.54
    comp = None if compression in ("none", "", None) else compression
    out: list[Path] = []
    for i, arr in enumerate(arrays):
        n = arr.shape[2]
        names = "\0".join(ink_names[:n]) + "\0"
        # Tag structure matched to printtarg's (which Photoshop opens), verified
        # against Photoshop directly (#72): Orientation set, one strip, InkNames +
        # NumberOfInks kept for RIP hand-off. Critically **InkSet is only written
        # for plain CMYK (=1)**; for >4 inks we omit it so it defaults to CMYK,
        # which makes Photoshop read the surplus inks as spot channels. Writing
        # InkSet=2 (not-CMYK) is exactly what made Photoshop reject the file.
        extratags = [
            (274, "H", 1, 1, True),                       # Orientation = top-left
            (334, "H", 1, n, True),                       # NumberOfInks
            (333, "s", 0, names, True),                   # InkNames (NUL-joined)
        ]
        if n == 4:
            extratags.append((332, "H", 1, 1, True))      # InkSet = CMYK
        kwargs = dict(photometric="separated", resolution=(res, res),
                      resolutionunit=3, compression=comp, extratags=extratags,
                      rowsperstrip=arr.shape[0])           # single strip, like printtarg
        if n > 4:
            # The inks past CMYK are declared "unspecified" — i.e. extra *ink*
            # data, not alpha. Verified against Photoshop (#72): "unassalpha"
            # made Photoshop treat them as transparency (paper = 0 ink → fully
            # transparent), while "unspecified" opens opaque. The one-time
            # earlier failure with "unspecified" was the InkSet=2 tag, now gone.
            kwargs["extrasamples"] = ("unspecified",) * (n - 4)
        path = base if len(arrays) == 1 else stem.parent / f"{stem.name}_{i + 1:02d}.tif"
        tifffile.imwrite(str(path), arr, **kwargs)
        out.append(path)
    return out


def save_tiffs(images: list[Image.Image], base_path: str | Path, dpi: int = 300,
               *, bit16: bool = False, compression: str = "lzw") -> list[Path]:
    """Write *images* as TIFF(s) in px/cm (ResolutionUnit=3); return paths.

    Single page → ``base.tif``; multiple → ``base_01.tif`` ….  *bit16* writes
    16-bit channels (8-bit values scaled up); *compression* is the tifffile
    codec name ("lzw", "zlib", or "none").
    """
    base = Path(base_path)
    stem = base.with_suffix("")
    res = dpi / 2.54  # pixels per centimetre, matching printtarg
    comp = None if compression in ("none", "", None) else compression
    out: list[Path] = []
    for i, img in enumerate(images):
        arr = np.asarray(img)
        if bit16:
            arr = (arr.astype(np.uint16) * 257)   # 8-bit → 16-bit (×257)
        path = base if len(images) == 1 else stem.parent / f"{stem.name}_{i + 1:02d}.tif"
        tifffile.imwrite(
            str(path), arr, photometric="rgb",
            resolution=(res, res), resolutionunit=3, compression=comp,
        )
        out.append(path)
    return out


def row_label_band_mm(geom, *, dpi: int, rows: int = 0,
                      indicator_font: str = DEFAULT_INDICATOR_FONT,
                      indicator_size_mm: float = 0.0,
                      indicator_bold: bool = False,
                      indicator_italic: bool = False,
                      patch_pattern: str = "",
                      gap_mm: float = 1.0) -> float:
    """How wide the row-label band has to be, for THESE labels at THIS size.

    §R1.2: *"Their position follows Text distance to edge and the Clip setting
    — it is not a fixed 7.5 mm, because the label text size varies."* The band
    was `ROW_LABEL_BAND_MM = 7.5` whatever the size and however many rows there
    were, so 16 pt labels walked toward the paper edge while the reservation
    stayed put, and a three-digit row number walked off it.

    Measured from the WIDEST label actually drawn — the last row's — at the
    resolved indicator size, plus Knut's *"maybe 1 millimetre space to the
    left of the letters"*.

    Lives here rather than in `geometry` because this is where the fonts are;
    `geometry` calls it lazily, the same way it already reaches this module for
    the furniture reserves.

    THE COUNT IS AN ALLOWANCE, NOT THE ACTUAL ROWS. Sizing the band from the
    rows that fit makes it depend on the patch size — which in area-first is
    derived FROM the usable width, which the band has just changed. Measured
    on a ColorMunki: the provisional geometry (auto patch size, many small
    rows) asked for 9.43 mm and the finished one for 5.22 mm, so the width the
    patch size was derived from was not the width the page ended up with.
    Knut's rule is that the band follows the TEXT SIZE; the row count only
    decides how many characters. So the allowance is the widest label from
    1 to 99 — two characters, which is what a page of patches actually holds
    (ten to thirty rows is the normal range) and keeps the band close to the
    7.5 mm it replaces instead of taking another 3 mm of margin for a third
    digit almost no chart prints.

    A page that somehow holds more than 99 rows is not left to walk off the
    paper: the renderer clamps the label at the same floor this band is
    measured from, so a wider label eats into its own gap rather than the
    page edge.
    """
    mm2px = dpi / 25.4
    ind_px = max(6, round(effective_indicator_size_mm(
        geom, dpi, indicator_font, indicator_size_mm) * mm2px))
    font = _font(ind_px, indicator_font, indicator_bold, indicator_italic)
    label = permutation.make_labeller(
        patch_pattern or permutation.DEFAULT_PATCH_PATTERN)
    img = Image.new("L", (1, 1))
    draw = ImageDraw.Draw(img)
    # The widest of the labels that will really be printed, not an assumption
    # about digits: a letter pattern makes "AA" wider than "10".
    widest = 0.0
    for r in (1, 9, 99) if rows <= 0 else range(1, rows + 1):
        widest = max(widest, float(draw.textlength(label(r), font=font)))
    return widest / mm2px + max(0.0, gap_mm)
