"""The clip-border text and the wordmark share one centre line across the band
(Basti, 2026-10-25, on Knut's forum post 149832: *"Should the text not also be
aligned to the centre, like the logo, so they follow each other?"*).

Only the content moves: the row labels, the strip letters, the margins and the
patch count are laid out against where the content reached BEFORE it was
centred, and the centred ink never passes that reach.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                             # noqa: E402
import pytest                                                  # noqa: E402

from workflow.layout_engine import geometry, instruments, raster  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe        # noqa: E402

from tests.test_row_labels_use_the_free_part_of_the_clip_border import KNUT  # noqa: E402,E501

DPI = 200
MM = DPI / 25.4
T2 = KNUT["clip_text"]
T4 = (T2 + "\n{instrument} - {patchcount} - {page} - {date}"
           "\n{instrument} - {patchcount} - {page} - {date}")


def _setup(new, width, text, scale, mode="branding"):
    r = LayoutRecipe.from_dict(dict(
        KNUT, clip_border_free_space=new, clip_border_width_mm=width,
        clip_text=text, clip_image_scale=scale, clip_content_mode=mode))
    kw = dict(r.build_kwargs(), area_target_count=600)
    g = instruments.geom_from_build_kwargs(kw)
    area = geometry.clip_area_px(g, 150.0, DPI, 100.0, 0, 0.0)
    return g, kw, area


def _strip(g, area, text, scale, centre=True, mode="branding"):
    ax, _ay, aw, ah = area
    return raster.render_clip_strip(
        mode, width_px=aw, height_px=ah, dpi=DPI, text=text,
        font_family="JetBrains Mono", text_size_mm=2.12, image_scale=scale,
        centre_across=centre,
        inner_limit_px=(raster._clip_inner_limit_px(g, ax, aw, DPI)
                        if centre else 0.0))


def _cols(img):
    a = np.asarray(img.convert("RGB")).astype(int).min(axis=2) < 200
    c = np.nonzero(a.any(axis=0))[0]
    return c[0], c[-1] + 1


def _split(img):
    """(text part, wordmark part): the wordmark is drawn at the band's
    bottom end, the lines in the box above it."""
    h = img.height
    return img.crop((0, 0, img.width, h - int(40 * MM))), \
        img.crop((0, h - int(30 * MM), img.width, h))


@pytest.mark.parametrize("scale", [100.0, 150.0])
@pytest.mark.parametrize("text", [T2, T4])
def test_his_13_mm_band_centres_the_lines_and_the_wordmark_together(
        text, scale):
    g, _kw, area = _setup(False, 13.0, text, scale)
    strip = _strip(g, area, text, scale)
    centre = area[2] / 2.0
    lines, mark = _split(strip)
    for part in (lines, mark):
        a, b = _cols(part)
        assert abs((a + b) / 2.0 - centre) <= 0.25 * MM, (a / MM, b / MM)


def test_before_the_lines_hugged_the_page_edge_side():
    g, _kw, area = _setup(False, 13.0, T2, 150.0)
    a, _b = _cols(_split(_strip(g, area, T2, 150.0, centre=False))[0])
    a2, _b2 = _cols(_split(_strip(g, area, T2, 150.0))[0])
    assert a < 0.5 * MM < a2


def test_lines_too_thick_for_the_band_still_start_at_clip():
    g, _kw, area = _setup(False, 11.0, T4, 150.0)
    a, _b = _cols(_split(_strip(g, area, T4, 150.0))[0])
    a0, _b0 = _cols(_split(_strip(g, area, T4, 150.0, centre=False))[0])
    assert a == a0


@pytest.mark.parametrize("width,text,scale", [
    (11.0, T2, 100.0), (11.0, T2, 150.0), (13.0, T2, 100.0),
    (13.0, T4, 100.0), (13.0, T4, 150.0)])
def test_the_labels_keep_their_place_and_their_one_millimetre(
        width, text, scale):
    """New-rule recipes: the labels are placed against the UNCENTRED reach,
    and the centred ink never passes it."""
    g, kw, area = _setup(True, width, text, scale)
    ax = area[0]
    uncentred = _strip(g, area, text, scale, centre=False)
    _a, b0 = _cols(uncentred)
    assert g.clip_content_reach_mm == pytest.approx((ax + b0) / MM, abs=0.02)
    _a, b = _cols(_strip(g, area, text, scale))
    assert (ax + b) / MM <= g.clip_content_reach_mm + 1e-6


def test_the_reach_the_layout_reads_is_the_uncentred_one(monkeypatch):
    seen = []
    real = raster.render_clip_strip

    def spy(*a, **k):
        seen.append(k.get("centre_across", True))
        return real(*a, **k)
    monkeypatch.setattr(raster, "render_clip_strip", spy)
    raster._clip_reach_cached.cache_clear()
    g, kw, _area = _setup(True, 12.5, T2, 125.0)
    assert seen and not any(seen)


def test_plain_text_is_centred_too():
    g, _kw, area = _setup(False, 13.0, T2, 100.0, mode="text")
    strip = _strip(g, area, T2, 100.0, mode="text")
    a, b = _cols(strip)
    assert abs((a + b) / 2.0 - area[2] / 2.0) <= 0.25 * MM


def test_large_lines_share_the_wordmarks_ink_centre_line(tmp_path):
    # Review of 4.3.15, measured on the sheet: four lines at 9 pt in a 20 mm
    # band were centred on their line boxes, which carry descender room, and
    # their ink sat 0.3 mm off the wordmark's ink-centred line (11.30 mm
    # against 10.99). Both are now centred on their ink.
    from tests.test_row_labels_use_the_free_part_of_the_clip_border import \
        _render
    kw = dict(clip_border_free_space=False, clip_border_width_mm=20.0,
              clip_text=T4, clip_image_scale=150.0, clip_image_offset_x_mm=0.0,
              clip_image_offset_y_mm=0.0, clip_text_size_mm=9 * 25.4 / 72)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    full = _render(tmp_path / "a", **kw)[40:1100, :round(20 * MM)].astype(int)
    mark = _render(tmp_path / "b", **dict(kw, clip_text=""))[
        40:1100, :round(20 * MM)].astype(int)
    lines = (full != mark) & (full < 200)
    wm = mark < 200

    def centre(m):
        c = np.nonzero(m.any(axis=0))[0]
        return (c[0] + c[-1] + 1) / 2.0
    assert abs(centre(lines) - centre(wm)) <= 1.0   # px, 0.13 mm
