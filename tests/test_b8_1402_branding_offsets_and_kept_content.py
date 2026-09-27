"""B8-1402 (challenge 9 of beta 44), two faults in the clip border.

(a) An Offset Y moved the ChromIQ branding wordmark over its own text: the
    offsets moved the wordmark, while the text box was measured from where the
    wordmark would be unmoved. The box's near edge now follows the moved
    wordmark's last ink plus the 3.5 mm gap (K58), and never runs past the
    strip. Offset X moves the wordmark across the band; the lines stay centred
    in it, and cannot meet it because the box ends before it along the band.
(b) `LayoutRecipe.build_kwargs` / `from_build_kwargs` did not carry
    `clip_content_when_on` (K57, B8-1388), so a chart restored from its build
    settings lost the kind its clip border takes when switched On.

Mutations (each run red): M1402-a the box measured from the unmoved wordmark
again (no `+ round(offset_y_px)`); M1402-b no `min(L, ...)` (a wordmark moved
down lets the box run off the strip); M1402-c `build_kwargs` drops the key;
M1402-d `from_build_kwargs` drops the key; M1402-e `build_chart` without the
parameter.
"""
from __future__ import annotations

import inspect

import numpy as np
import pytest

from workflow.layout_engine import raster
from workflow.layout_engine.presets import LayoutRecipe, default_recipe

DPI = 200
MM = DPI / 25.4
PAGE_MM = 297.0
LONG = ("Hahnemuehle Photo Rag 308 gsm, Epson SureColor P900, profiled "
        "2026-08-21 by Knut, run 3 of the verification series. ") * 3


def _pink(arr):
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    return ((r - g) > 40) & (b > g)


def _ink(arr):
    return arr.sum(axis=2) < 700


def _span(rows):
    idx = np.nonzero(rows)[0]
    return (int(idx[0]), int(idx[-1])) if idx.size else None


def _band(offset_y_mm: float, offset_x_mm: float = 0.0, text: str = LONG,
          band_mm: float = 24.0):
    img = raster.render_clip_strip(
        "branding", width_px=int(round(band_mm * MM)),
        height_px=int(round(PAGE_MM * MM)), dpi=DPI, text=text,
        image_offset_x_mm=offset_x_mm, image_offset_y_mm=offset_y_mm)
    return np.asarray(img.convert("RGB")).astype(int)


def _wordmark_top(arr) -> int:
    """The wordmark's far end along an upright band: its magenta "IQ"."""
    pink = _span(_pink(arr).any(axis=1))
    assert pink is not None, "no wordmark on the band"
    return pink[0]


@pytest.mark.parametrize("oy", [-120.0, -60.0, -20.0, -5.0, 0.0])
def test_an_offset_y_toward_the_text_keeps_the_gap(oy):
    arr = _band(oy)
    top = _wordmark_top(arr)
    above = arr[:top]
    text_rows = _span(_ink(above).any(axis=1))
    assert text_rows is not None, "the text is gone"
    gap_mm = (top - text_rows[1]) / MM
    assert gap_mm >= 3.0, (
        f"Offset Y {oy} mm: the text ends {gap_mm:.1f} mm from the wordmark; "
        "it must keep the 3.5 mm gap, never run under it")


@pytest.mark.parametrize("oy", [5.0, 20.0])
def test_an_offset_y_away_from_the_text_lets_the_box_follow(oy):
    """Moved toward the bottom end, the wordmark takes the gap with it, and
    the box grows with it without running off the strip."""
    arr = _band(oy)
    top = _wordmark_top(arr)
    text_rows = _span(_ink(arr[:top]).any(axis=1))
    gap_mm = (top - text_rows[1]) / MM
    assert 3.0 <= gap_mm <= 5.0, gap_mm


def test_a_wordmark_moved_off_the_strip_leaves_a_box_no_longer_than_the_strip():
    arr = _band(400.0, text="Epson P900")
    # the lines are still drawn, inside the strip
    rows = _span(_ink(arr).any(axis=1))
    assert rows is not None and rows[0] >= 0 and rows[1] < arr.shape[0]


def test_offset_x_moves_the_wordmark_across_and_the_text_stays_clear():
    arr = _band(-40.0, offset_x_mm=4.0)
    top = _wordmark_top(arr)
    text_rows = _span(_ink(arr[:top]).any(axis=1))
    assert (top - text_rows[1]) / MM >= 3.0


def test_the_generated_page_keeps_the_gap_with_an_offset_y():
    """On the page Generate draws (`render_pages`), not only the band."""
    from workflow.layout_engine import geometry, instruments
    from workflow.layout_engine.ti1_reader import ColorTarget
    r = default_recipe("i1", "A4", mode="clip")
    geom = instruments.geom_from_build_kwargs(r.build_kwargs())
    target = ColorTarget(
        color_rep="iRGB", device_fields=["RGB_R", "RGB_G", "RGB_B"],
        patches=[((float(i * 9 % 100), float(i * 17 % 100), float(i * 5 % 100)),
                  (40.0, 45.0, 50.0)) for i in range(60)])
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    dpi = 100

    def band(text):
        res = raster.render_pages(
            target, lay, geom, seed=1, randomize=False, paper_w_mm=210.0,
            paper_h_mm=297.0, dpi=dpi, clip_content_mode="branding",
            clip_text=text, clip_image_offset_y_mm=-60.0)
        page = np.asarray(res.images[0].convert("RGB")).astype(int)
        ax, ay, aw, ah = geometry.clip_area_px(geom, 297.0, dpi, 210.0, 0, 0.0)
        return _ink(page[ay:ay + ah, ax:ax + aw])
    # the wordmark alone, then the lines as what the text adds to it
    mark = band("")
    lines = band(LONG) & ~mark
    wm = _span(mark.any(axis=1))
    txt = _span(lines.any(axis=1))
    assert wm and txt
    assert txt[1] < wm[0], "the lines run under the wordmark"
    assert (wm[0] - txt[1]) / (dpi / 25.4) >= 3.0


@pytest.mark.parametrize("kind", ["branding", "text", "image", ""])
def test_the_kept_content_travels_in_the_build_settings(kind):
    r = LayoutRecipe(instrument="CM", paper="A4")
    r.clip_content_mode = "off"
    r.clip_content_when_on = kind
    kw = r.build_kwargs()
    assert kw["clip_content_when_on"] == kind
    back = LayoutRecipe.from_build_kwargs(kw)
    assert back.clip_content_when_on == kind
    assert LayoutRecipe.from_dict(kw).clip_content_when_on == kind


def test_build_settings_written_before_read_as_the_notes_box():
    kw = LayoutRecipe(instrument="CM").build_kwargs()
    kw.pop("clip_content_when_on")
    assert LayoutRecipe.from_build_kwargs(kw).clip_content_when_on == ""


def test_the_engine_accepts_every_build_setting():
    from workflow.layout_engine import chart
    params = inspect.signature(chart.build_chart).parameters
    missing = [k for k in LayoutRecipe().build_kwargs() if k not in params]
    assert not missing, missing
