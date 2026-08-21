"""#163 — the clip-border branding must print the branding AND the user's lines.

soul-traveller: *"the clip-border ChromIQ branding option ... shows the icon
only if there is no text, and if there is text only the text without the icon
is shown"*.

The wordmark never vanished outright: it lost a fight it could not win. The
fit-to-band loop shrank ONLY the wordmark, so with a clip-text size set every
millimetre the lines took came out of the branding until it was a few pixels
tall — and once the lines alone were larger than the band, the loop ran out of
steps and they were printed off the edge of the sheet.

Two kinds of test here, because each catches what the other cannot:

* the RULE, against :func:`_fit_branding_sizes` — exact sizes, so a fix that is
  subtly too greedy for the wordmark, or that quietly shrinks a size the user
  asked for, fails here rather than hiding inside a tolerance;
* the PICTURE, against the rendered band — every line present, nothing cut off,
  the branding actually inked, which is all the printed sheet really promises.
"""
from __future__ import annotations

import numpy as np
import pytest

from workflow.layout_engine import raster
from workflow.layout_engine.raster import (_CLIP_ACROSS, _CLIP_ALONG,
                                           _WORDMARK_FLOOR_FRAC,
                                           _fit_branding_sizes)

DPI = 200
MM = DPI / 25.4
PAGE_MM = 297.0
LINES = ["Knut Petersen", "Epson P900", "Hahnemuehle Photo Rag",
         "Glossy 310", "2026-08-21", "run 3"]
LONG_LINE = "Hahnemuehle Photo Rag 308 gsm " * 8          # 240 characters

# The band widths and clip-text sizes the UI can actually produce: the clip-width
# spin starts at 10 mm (layout_options_panel: clip_width.setMinimum) and the size
# spin runs to 72 pt = 25.4 mm. The first version of these tests stopped at 12 mm
# and 8 mm — inside the old shrink loop's reach, which is why it missed that the
# loop could not converge.
BANDS = [10, 12, 16, 20, 24, 30, 40]
SIZES = [0.0, 2.0, 3.0, 4.23, 6.0, 8.0, 14.0, 25.4]
COUNTS = [0, 1, 2, 3, 5, 6]


# ---------------------------------------------------------------------------
# the rule
# ---------------------------------------------------------------------------

def _fit(band_mm: float, size_mm: float, nlines: int, lines=None):
    w = int(round(band_mm * MM))
    return _fit_branding_sizes(
        list(lines if lines is not None else LINES[:nlines]), w,
        int(round(PAGE_MM * MM)), "Inter", size_mm * MM), w


@pytest.mark.parametrize("band_mm", BANDS)
@pytest.mark.parametrize("size_mm", SIZES[1:])
@pytest.mark.parametrize("nlines", COUNTS)
def test_the_stack_always_fits_across_the_band(band_mm, size_mm, nlines):
    """Whatever the user asks for, the stack fits — it is never printed off the
    band. The old loop stepped 40 × 0.95, which bottoms out at ×0.129, so a size
    far above what the band holds still overflowed."""
    (size, esize), w = _fit(band_mm, size_mm, nlines)
    stack = size * 1.25 + nlines * esize * 1.25
    assert stack <= w * _CLIP_ACROSS + 1, (
        f"stack {stack:.0f}px over a {w}px band (wordmark {size}, lines {esize})")


@pytest.mark.parametrize("band_mm,size_mm,nlines", [
    (24, 2.0, 1), (24, 3.0, 3), (30, 4.23, 3), (40, 6.0, 3), (24, 4.23, 1),
    (16, 2.0, 2), (40, 8.0, 2),
])
def test_a_size_that_fits_is_used_exactly_as_asked(band_mm, size_mm, nlines):
    """The cap may only bite when it has to. A clip-text size the band can hold
    is rendered at that size — not a few per cent under it."""
    (_size, esize), _w = _fit(band_mm, size_mm, nlines)
    assert esize == int(size_mm * MM), (
        f"asked {size_mm} mm ({int(size_mm * MM)}px), got {esize}px")


@pytest.mark.parametrize("band_mm", BANDS)
@pytest.mark.parametrize("size_mm", SIZES[1:])
@pytest.mark.parametrize("nlines", [1, 2, 3, 5, 6])
def test_the_wordmark_never_takes_more_than_its_floor(band_mm, size_mm, nlines):
    """The branding is protected, not privileged.

    Once the user's lines have to be shrunk, the wordmark must be sitting at its
    floor — an equal share of the band, and never more than
    ``_WORDMARK_FLOOR_FRAC`` of its unconstrained size. A greedier floor would
    quietly halve the user's text to make the logo bigger.
    """
    (size, esize), w = _fit(band_mm, size_mm, nlines)
    if esize >= int(size_mm * MM):
        return                       # the user's size survived; nothing to trade
    floor = min(w * _CLIP_ACROSS / (1 + nlines) / 1.25,
                w * 0.55 * _WORDMARK_FLOOR_FRAC)
    assert size <= floor + 1, (
        f"the wordmark took {size}px (floor {floor:.0f}px) while shrinking the "
        f"user's lines to {esize}px")


@pytest.mark.parametrize("band_mm", BANDS)
@pytest.mark.parametrize("size_mm", SIZES[1:])
def test_neither_block_overruns_the_strip_length(band_mm, size_mm):
    """Along the strip, with a line far too long for the page."""
    (size, esize), _w = _fit(band_mm, size_mm, 3, lines=[LONG_LINE, "b", "c"])
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    along = PAGE_MM * MM * _CLIP_ALONG
    f = raster._font(size, raster.WORDMARK_FONT)
    wm = d.textlength("Chrom", font=f) + d.textlength("IQ", font=f) * 1.25
    txt = d.textlength(LONG_LINE, font=raster._font(esize, "Inter"))
    assert wm <= along + 2, f"the wordmark is {wm:.0f}px along a {along:.0f}px strip"
    assert txt <= along + 2, f"the line is {txt:.0f}px along a {along:.0f}px strip"


def test_the_wordmark_itself_is_capped_by_the_strip_length():
    """A band wide enough that the WORDMARK is what does not fit lengthways.

    No paper reaches this — the widest clip band the UI allows is 100 mm and the
    shortest page is far longer — but it is the other half of the same rule, and
    without it nothing stops the wordmark being sized for the band alone and
    running off both ends of the strip.
    """
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    size, esize = _fit_branding_sizes(["Lab"], 400, 300, "Inter", 40.0)
    f = raster._font(size, raster.WORDMARK_FONT)
    wm = d.textlength("Chrom", font=f) + d.textlength("IQ", font=f) * 1.25
    assert wm <= 300 * _CLIP_ALONG + 2, (
        f"the wordmark is {wm:.0f}px along a {300 * _CLIP_ALONG:.0f}px strip")
    assert size * 1.25 + esize * 1.25 <= 400 * _CLIP_ACROSS + 1


def test_a_long_line_of_the_users_does_not_shrink_the_wordmark():
    """The two axes are separate. A line too long for the STRIP is the line's
    problem — shrinking the wordmark does nothing to relieve it, and costs the
    branding for free."""
    short, _w = _fit(24, 4.23, 1, lines=["Lab"])
    long_, _w = _fit(24, 4.23, 1, lines=[LONG_LINE])
    assert long_[0] == short[0], (
        f"a 240-character line shrank the wordmark from {short[0]} to {long_[0]}")


@pytest.mark.parametrize("band_mm,nlines,expect", [
    (24, 0, 103), (24, 1, 65), (24, 3, 32), (16, 3, 21), (40, 5, 36),
])
def test_the_automatic_size_is_untouched(band_mm, nlines, expect):
    """With no size set, wordmark and lines share one auto-fitted size — the
    long-standing behaviour, pinned exactly. #163 is about the case where a size
    IS set; the default must come through the fix unchanged."""
    (size, esize), _w = _fit(band_mm, 0.0, nlines)
    assert size == esize == expect


# ---------------------------------------------------------------------------
# the picture
# ---------------------------------------------------------------------------

def _band(band_mm: float, size_mm: float, nlines: int, font: str = "Inter"):
    w = int(round(band_mm * MM))
    img = raster.render_clip_strip(
        "branding", width_px=w, height_px=int(round(PAGE_MM * MM)), dpi=DPI,
        text="\n".join(LINES[:nlines]), font_family=font, text_size_mm=size_mm)
    return np.asarray(img.convert("RGB")).astype(int), w


def _ink_rows(arr: np.ndarray) -> list[tuple[int, int]]:
    """Contiguous inked bands ACROSS the strip = one per rendered line."""
    cols = (arr.sum(axis=2) < 700).any(axis=0)
    rows, start = [], None
    for i, v in enumerate(cols):
        if v and start is None:
            start = i
        elif not v and start is not None:
            rows.append((start, i - 1))
            start = None
    if start is not None:
        rows.append((start, len(cols) - 1))
    return rows


def _wordmark_row(arr: np.ndarray, rows: list[tuple[int, int]]):
    """The row carrying the magenta "IQ" — the branding.

    Finding it by colour has a trap at each end. A loose distance to
    (255, 69, 115) — say |c - magenta| < 200 — also matches a mid-grey around
    115, i.e. the antialiased edge of ordinary BLACK text, so every line of the
    user's text looks like the wordmark. A tight distance finds nothing once the
    glyph is small enough that no pixel is fully covered. So test for PINKNESS
    instead: magenta over white keeps red well above green whatever the
    coverage, while any grey has red == green.
    """
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    cols = (((r - g) > 40) & (b > g)).any(axis=0)
    return next((row for row in rows if cols[row[0]:row[1] + 1].any()), None)


def test_wordmark_survives_a_fixed_clip_text_size():
    """soul-traveller's own settings: a 24 mm band, three lines at 6 mm.

    Before the fix the wordmark was shrunk to 9 px — about 1 mm on paper, which
    is what "only the text is shown" looked like."""
    arr, _w = _band(24, 6.0, 3)
    rows = _ink_rows(arr)
    wm = _wordmark_row(arr, rows)
    assert wm is not None, "the ChromIQ wordmark is not on the band at all"
    assert len([r for r in rows if r is not wm]) == 3, "one row per line of text"
    assert (wm[1] - wm[0] + 1) / MM >= 3.0, (
        f"the wordmark is only {(wm[1] - wm[0] + 1) / MM:.1f} mm tall")


@pytest.mark.parametrize("band_mm", BANDS)
@pytest.mark.parametrize("size_mm", SIZES)
@pytest.mark.parametrize("nlines", COUNTS)
def test_branding_band_never_starves_or_clips(band_mm, size_mm, nlines):
    """Cross every band width, clip-text size and line count.

    On the printed band, whatever the combination: every line is there, none of
    it is cut off at the band edges, and the branding is inked.
    """
    arr, w = _band(band_mm, size_mm, nlines)
    rows = _ink_rows(arr)
    assert len(rows) == nlines + 1, (
        f"{len(rows)} ink rows on the band, expected {nlines + 1} "
        "(the wordmark plus one per line) — a line is missing or two merged")
    assert rows[0][0] > 0 and rows[-1][1] < w - 1, (
        "the content is cut off at the edge of the clip band")
    assert _wordmark_row(arr, rows) is not None, (
        "the ChromIQ wordmark is not on the band at all")
