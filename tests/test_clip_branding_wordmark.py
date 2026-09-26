"""The clip-border "ChromIQ branding": the wordmark AND the user's lines, with
the wordmark at the END of the band, where the Notes box puts its own.

#163 (soul-traveller): *"the clip-border ChromIQ branding option ... shows the
icon only if there is no text, and if there is text only the text without the
icon is shown"*. The wordmark lost a fight for the band's width it could not
win.

K58 (Knut, #182 5730034611, and 5848747795 when he found it still missing):
the wordmark was centred along the strip with the lines stacked ACROSS the band
beside it, so every line of text made it smaller. His design: *"placed in the
same way as for the "Notes box", at the bottom of the clip-border text field
(given that Flip 180 is off), or when Flip 180 is ON it is placed on the top
side ... centred against the width of the clip-border text area ... 3 to 4 mm
space after the image before the text in Text field is placed"*, the text in
the box that is left. The #163 fitter that shared the band across went with
it: the wordmark is sized by the band alone now.

Two kinds of test:

* the BAND, from `render_clip_strip` itself: the wordmark at the bottom end,
  as large with six lines as with none, and every line present in the box
  beyond it, clear of the wordmark by the gap, not cut off;
* the PAGE, from `render_pages` on a real layout, Side Left and Right x Flip
  180 Off and On: the branding's wordmark at the same end as the Notes box's,
  in all four.
"""
from __future__ import annotations

import numpy as np
import pytest

from workflow.layout_engine import raster

DPI = 200
MM = DPI / 25.4
PAGE_MM = 297.0
LINES = ["Knut Petersen", "Epson P900", "Hahnemuehle Photo Rag",
         "Glossy 310", "2026-08-21", "run 3"]

# The band widths the UI can produce (the clip-width spin starts at 10 mm).
BANDS = [10, 12, 16, 20, 24, 30, 40]
COUNTS = [0, 1, 2, 3, 5, 6]


def _band(band_mm: float, nlines: int, size_mm: float = 0.0,
          font: str = "Inter"):
    w = int(round(band_mm * MM))
    img = raster.render_clip_strip(
        "branding", width_px=w, height_px=int(round(PAGE_MM * MM)), dpi=DPI,
        text="\n".join(LINES[:nlines]), font_family=font, text_size_mm=size_mm)
    return np.asarray(img.convert("RGB")).astype(int), w


def _pink(arr: np.ndarray) -> np.ndarray:
    """Pixels of the magenta "IQ". Magenta over white keeps red well above
    green whatever the coverage, while any grey (the black text's antialiased
    edge) has red == green."""
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    return ((r - g) > 40) & (b > g)


def _ink(arr: np.ndarray) -> np.ndarray:
    return arr.sum(axis=2) < 700


def _span(mask_rows: np.ndarray):
    idx = np.nonzero(mask_rows)[0]
    return (int(idx[0]), int(idx[-1])) if idx.size else None


def _wordmark_along(arr: np.ndarray):
    """Where the wordmark sits ALONG an upright band: from its top (the
    magenta "IQ", the far end of a wordmark that reads up the strip) to the
    last inked row of the band (its "C")."""
    pink = _span(_pink(arr).any(axis=1))
    assert pink is not None, "the ChromIQ wordmark is not on the band at all"
    last = _span(_ink(arr).any(axis=1))[1]
    return pink[0], last


def _runs(mask: np.ndarray) -> "list[tuple[int, int]]":
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


# ---------------------------------------------------------------------------
# the band
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("band_mm", BANDS)
@pytest.mark.parametrize("nlines", COUNTS)
def test_the_wordmark_sits_at_the_bottom_end_and_the_lines_in_the_box(
        band_mm, nlines):
    """Upright band (a left band, Flip 180 off): the wordmark against the
    bottom end, the lines above it, 3.5 mm clear of it, each one present and
    none cut off at the band's edges.

    MUTATION, proven red: centre the wordmark along the strip again
    (``x = (L - wm_w) / 2`` in `_vwordmark`)."""
    arr, w = _band(band_mm, nlines)
    H = arr.shape[0]
    lo, hi = _wordmark_along(arr)
    # 2 mm of end pad, as the Notes box has, plus the "C"'s own side bearing
    assert H - 1 - hi <= 4.0 * MM, (
        f"the wordmark ends {(H - 1 - hi) / MM:.1f} mm from the bottom end; "
        "the Notes box puts it 2 mm from it")
    box = arr[:max(0, lo - int(3.0 * MM))]
    rows = _runs(_ink(box).any(axis=0))
    assert len(rows) == nlines, (
        f"{len(rows)} lines of ink in the text box, expected {nlines}")
    if nlines:
        assert rows[0][0] > 0 and rows[-1][1] < w - 1, \
            "a line is cut off at the edge of the band"
        gap = lo - _span(_ink(box).any(axis=1))[1]
        assert gap >= 3.0 * MM, f"the text is {gap / MM:.1f} mm from the wordmark"


@pytest.mark.parametrize("band_mm", BANDS)
def test_text_never_shrinks_the_wordmark(band_mm):
    """Knut's complaint in one line: *"This results in a very small ChromIQ
    image, as it becomes smaller for every line of text written"*.

    MUTATION, proven red: size the wordmark by the number of lines
    (``size /= 1 + len(extra_lines)``)."""
    sizes = []
    for n in (0, 3, 6):
        arr, _w = _band(band_mm, n)
        lo, hi = _wordmark_along(arr)
        sizes.append(hi - lo)
    assert max(sizes) - min(sizes) <= 2, (
        f"the wordmark's length changes with the text: {sizes} px")


def test_a_typed_size_is_used_in_the_box():
    """A typed clip-text Size is the size of the lines (#125), in the box."""
    arr, _w = _band(24, 1, size_mm=4.0)
    lo, _hi = _wordmark_along(arr)
    box = arr[:lo - int(3.0 * MM)]
    across = _span(_ink(box).any(axis=0))
    assert across is not None
    height_mm = (across[1] - across[0] + 1) / MM
    assert 2.0 <= height_mm <= 4.5, f"a 4 mm line is {height_mm:.1f} mm tall"


def test_branding_extra_text_uses_chosen_font():
    """The lines use the chosen clip font, not the wordmark face (#93)."""
    a, _ = _band(24, 2, font="Inter")
    b, _ = _band(24, 2, font="JetBrains Mono")
    assert not np.array_equal(a, b)


# ---------------------------------------------------------------------------
# the page: Side Left / Right x Flip 180 Off / On, against the Notes box
# ---------------------------------------------------------------------------
def _page_band(mode: str, side: str, flip: bool) -> np.ndarray:
    """The clip band of a real page, rendered by the engine's page renderer
    (the one Generate uses), cut out by the band's own geometry."""
    from workflow.layout_engine import geometry, instruments
    from workflow.layout_engine.presets import default_recipe
    from workflow.layout_engine.ti1_reader import ColorTarget
    r = default_recipe("i1", "A4", mode="clip")
    r.clip_side = side
    geom = instruments.geom_from_build_kwargs(r.build_kwargs())
    target = ColorTarget(
        color_rep="iRGB", device_fields=["RGB_R", "RGB_G", "RGB_B"],
        patches=[((float(i * 9 % 100), float(i * 17 % 100), float(i * 5 % 100)),
                  (40.0, 45.0, 50.0)) for i in range(60)])
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    dpi = 100
    text = "Knut Larsson\nEpson P900" if mode == "branding" else ""
    res = raster.render_pages(
        target, lay, geom, seed=1, randomize=False, paper_w_mm=210.0,
        paper_h_mm=297.0, dpi=dpi, clip_content_mode=mode, clip_text=text,
        clip_flip_180=flip)
    page = np.asarray(res.images[0].convert("RGB")).astype(int)
    ax, ay, aw, ah = geometry.clip_area_px(geom, 297.0, dpi, 210.0, 0, 0.0)
    return page[ay:ay + ah, ax:ax + aw]


def _end_of_wordmark(band: np.ndarray) -> str:
    pink = _span(_pink(band).any(axis=1))
    assert pink is not None, "no wordmark on the page's clip band"
    mid = (pink[0] + pink[1]) / 2
    return "bottom" if mid > band.shape[0] / 2 else "top"


@pytest.mark.parametrize("side", ["left", "right"])
@pytest.mark.parametrize("flip", [False, True])
def test_the_branding_sits_at_the_same_end_as_the_notes_box(side, flip):
    """The four combinations Knut named, on the generated page: the branding's
    wordmark is at the end where the Notes box puts its own.

    MUTATION, proven red: centre the wordmark along the strip again."""
    notes = _page_band("notes", side, flip)
    brand = _page_band("branding", side, flip)
    assert _end_of_wordmark(brand) == _end_of_wordmark(notes)
    pn = _span(_pink(notes).any(axis=1))
    pb = _span(_pink(brand).any(axis=1))
    H = notes.shape[0]
    # at the very end: the branding's IQ lies within the outer quarter of the
    # strip, on the Notes box's side
    if _end_of_wordmark(notes) == "bottom":
        assert pb[1] > H * 0.75 and pn[1] > H * 0.75
    else:
        assert pb[0] < H * 0.25 and pn[0] < H * 0.25


def test_a_line_that_fills_the_box_keeps_the_gap_to_the_wordmark():
    """A line long enough to fill its box reaches the box's end, and the box
    ends 3 to 4 mm before the wordmark (Knut: "3 to 4 mm space after the
    image before the text").

    MUTATION, proven red: let the box run up to the wordmark
    (``box_len = int(L - (pad + ink_w))``)."""
    w = int(round(24 * MM))
    img = raster.render_clip_strip(
        "branding", width_px=w, height_px=int(round(PAGE_MM * MM)), dpi=DPI,
        text=("Hahnemuehle Photo Rag 308 gsm, Epson SureColor P900, "
              "profiled 2026-08-21 by Knut, run 3 of the verification series. ") * 3)
    arr = np.asarray(img.convert("RGB")).astype(int)
    lo, _hi = _wordmark_along(arr)
    box = arr[:lo]
    rows = _ink(box).any(axis=1)
    text_end = _span(rows)[1]
    gap_mm = (lo - text_end) / MM
    # the box starts 3.5 mm on; a line this long fills it (`_vtext` 99.5 %)
    assert 3.0 <= gap_mm <= 5.0, f"the text ends {gap_mm:.1f} mm before the wordmark"
