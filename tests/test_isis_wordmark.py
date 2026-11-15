"""The i1iSis chart carries THE ChromIQ wordmark, drawn by the engine's own
routine (`raster._draw_wordmark_h`), never the word typed as text (the owner,
2026-11-14, on the A4 preview: "the label exactly as on the other
instruments' charts").

Proved on rendered pages at 300 dpi: the routine is what draws it, "Chrom"
and the magenta italic "IQ" sit on one baseline within a pixel, that is the
name line's baseline too, and the "IQ" is the wordmark face's italic.
"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw

from workflow.isis import chart as C
from workflow.layout_engine import raster

DPI = 300
S = DPI / 25.4

CASES = [
    # (patches, paper w, h, extra options)
    (957, 210, 297, {}),
    (957, 210, 297, {C.LETTERS_KEY: "top", "draw_indicators": True}),
    (957, 216, 279, {"isis_tight": True}),
    (2000, 210, 297, {}),                        # two pages
    (957, 330, 483, {"isis_model": "xl"}),
    (63, 100, 200, {}),                          # a small custom sheet
]


def _layout(n, w, h, extra):
    return C.layout_for(n, w, h, {**extra, C.COUNT_KEY: n,
                                  "paper": f"{w}x{h}"})


def _page(n, w, h, extra, page=0):
    _o, g, sheet = _layout(n, w, h, extra)
    items, _off = C.plan_page(sheet, page, name="iSis-wordmark",
                              title="iSis-wordmark")
    img = Image.new("RGB", (int(round(w * S)), int(round(h * S))), "white")
    geom: list = []
    C.draw_page(img, geom, sheet, items, DPI)
    return g, sheet, items, img, geom


def _masks(img, wm):
    x, y, bw, bh = wm.box
    # from the ink box's top: the dashed outline ends 0.25 mm above it
    x0, y0 = int(x * S) - 3, int(y * S) - 1
    # one pixel past the ink box below: the strip letters' zone starts
    # 0.25 mm (3 px) under it
    a = np.asarray(img).astype(int)[y0:int((y + bh) * S) + 2,
                                    x0:int((x + bw) * S) + 4]
    dark = a.sum(axis=2) < 250
    r, gg, b = raster.WORDMARK_IQ_RGB
    magenta = ((abs(a[..., 0] - r) < 70) & (abs(a[..., 1] - gg) < 70)
               & (abs(a[..., 2] - b) < 70) & ~dark)
    return x0, y0, dark, magenta


@pytest.mark.parametrize("n,w,h,extra", CASES)
def test_every_page_carries_the_wordmark_and_no_typed_ChromIQ(n, w, h,
                                                              extra):
    _o, g, sheet = _layout(n, w, h, extra)
    for page in range(g.P):
        items, _off = C.plan_page(sheet, page, name="iSis-wordmark",
                                  title="iSis-wordmark")
        marks = [i for i in items if i.kind == "wordmark"]
        assert len(marks) == 1, page
        line = [i for i in items if i.role == "name_line"][0]
        assert "ChromIQ" not in line.text
        # one baseline for the text and the wordmark
        assert line.pen[1] == pytest.approx(marks[0].pen[1])
        assert C.keep_out_violations(sheet, items) == []


def test_the_engine_routine_draws_it(monkeypatch):
    calls = []
    real = raster._draw_wordmark_h

    def spy(*a, **k):
        calls.append(a[4])                # the band height
        return real(*a, **k)

    monkeypatch.setattr(raster, "_draw_wordmark_h", spy)
    C._WM_CACHE.clear()
    _g, _sheet, items, img, geom = _page(957, 210, 297, {})
    assert calls, "the wordmark was not drawn by raster._draw_wordmark_h"
    # never a text run in the vector page either
    assert not any(e[0] == "text" and "ChromIQ" in str(e[3]) for e in geom)
    # it reaches the PDF and the separated TIFF as artwork
    wm = [i for i in items if i.kind == "wordmark"][0]
    clips = [e for e in geom if e[0] == "clip"]
    assert any(abs(e[1][0] - wm.pen[0] * S) < 4 * S for e in clips)
    C._WM_CACHE.clear()


@pytest.mark.parametrize("n,w,h,extra", CASES)
def test_chrom_and_IQ_sit_on_the_name_lines_baseline(n, w, h, extra):
    g, _sheet, items, img, _geom = _page(n, w, h, extra,
                                         page=min(1, _layout(n, w, h, extra)
                                                  [1].P - 1))
    wm = [i for i in items if i.kind == "wordmark"][0]
    x0, y0, dark, magenta = _masks(img, wm)
    assert magenta.sum() > 20, "no magenta IQ"
    cols_d = np.where(dark.any(axis=0))[0]
    cols_m = np.where(magenta.any(axis=0))[0]
    # "m", the last letter of Chrom (flat serifs on the baseline), and "I",
    # the first of IQ (the Q's tail runs below it)
    m = cols_d[int(len(cols_d) * 0.82):]
    i_ = cols_m[:max(2, len(cols_m) // 5)]

    def bottom(mask, cols):
        rows = np.where(mask[:, cols.min():cols.max() + 1].any(axis=1))[0]
        return rows.max() + y0

    base = int(round(wm.pen[1] * S))
    assert abs(bottom(dark, m) - bottom(magenta, i_)) <= 1
    assert abs(bottom(dark, m) - (base - 1)) <= 1
    # the IQ follows Chrom, never overlapping it
    assert cols_m.min() > cols_d[int(len(cols_d) * 0.5)]


def test_the_IQ_is_the_wordmark_face_italic():
    _g, _sheet, items, img, _geom = _page(957, 210, 297, {})
    wm = [i for i in items if i.kind == "wordmark"][0]
    _x0, _y0, _dark, magenta = _masks(img, wm)
    rows = np.where(magenta.any(axis=1))[0]
    cols = np.where(magenta.any(axis=0))[0]
    got = (cols.max() - cols.min() + 1, rows.max() - rows.min() + 1)
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    f, *_rest = raster._wordmark_h_fit(d, wm.size * S, 1e9)
    f_iq = raster._font(f.size, raster.WORDMARK_FONT, italic=True)
    tile, _b, _l = raster._italic_tile("IQ", f_iq,
                                       raster.WORDMARK_IQ_RGB + (255,),
                                       shear=0.0)
    box = tile.getbbox()
    want = (box[2] - box[0], box[3] - box[1])
    assert abs(got[0] - want[0]) <= 2 and abs(got[1] - want[1]) <= 2, \
        (got, want)
    # and it is NOT the upright face at that size
    up = raster._font(f.size, raster.WORDMARK_FONT)
    ub = d.textbbox((0, 0), "IQ", font=up)
    assert (ub[2] - ub[0], ub[3] - ub[1]) != want


def test_the_notes_band_names_the_i1iSis_and_its_own_page(monkeypatch):
    """The notes band (the engine's notes design, with its own wordmark)
    is drawn for every page: page 2 says 2/N, not page 1's 1/N, and it
    names the instrument as i1Profiler does, never the code XRISIS."""
    seen = []

    def fake(box, dpi, *, ctx=None, **_k):
        seen.append(dict(ctx or {}))
        return None

    monkeypatch.setattr(C, "band_image", fake)
    _o, g, sheet = _layout(2000, 210, 297, {C.BAND_KEY: True,
                                            C.BAND_PLACE_KEY: "trailer",
                                            C.BAND_HEIGHT_KEY: 24})
    assert g.P >= 2

    class Render:
        images = [Image.new("RGB", (int(210 * 50 / 25.4),
                                    int(297 * 50 / 25.4)), "white")
                  for _ in range(g.P)]
        patch_geom = None

    C.draw_furniture(Render(), sheet, 50, name="two", band={"ctx": {}})
    assert [c["page"] for c in seen] == [f"{i + 1}/{g.P}"
                                         for i in range(g.P)]
    assert {c["instrument"] for c in seen} == {"i1iSis"}
    assert {c["strips"] for c in seen} == {str(g.R)}
